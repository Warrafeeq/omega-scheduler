"""
MapReduce Scheduler: Opportunistic resource allocation for MapReduce jobs
"""
from typing import Optional, Dict
import time
from schedulers.base_scheduler import BaseScheduler
from core.cell_state import CellState, Job, Task, Transaction, Machine


class MapReduceScheduler(BaseScheduler):
    """
    Specialized scheduler for MapReduce jobs.
    Opportunistically uses idle cluster resources to speed up jobs.
    """
    
    def __init__(self, scheduler_id: str, cell_state: CellState,
                 policy: str = 'max_parallelism'):
        super().__init__(
            scheduler_id=scheduler_id,
            cell_state=cell_state,
            decision_time_per_job=0.2,
            decision_time_per_task=0.01
        )
        self.policy = policy  # 'max_parallelism', 'global_cap', 'relative_job_size'
        self.target_utilization = 0.6  # For global_cap policy
        self.max_scale_factor = 4.0  # For relative_job_size policy
        self.job_history: Dict[str, Dict] = {}  # Historical performance data
    
    def schedule_job(self, job: Job, snapshot: CellState) -> Optional[Transaction]:
        """Schedule MapReduce job with opportunistic scaling"""
        transaction = Transaction(self.scheduler_id)
        
        time.sleep(self.decision_time_per_job + 
                  self.decision_time_per_task * len(job.tasks))
        
        # Calculate available resources
        utilization = self._calculate_utilization(snapshot)
        available_resources = self._get_available_resources(snapshot)
        
        # Determine optimal worker count based on policy
        optimal_workers = self._calculate_optimal_workers(
            job, available_resources, utilization
        )
        
        # Schedule tasks up to optimal worker count
        tasks_to_schedule = job.tasks[:optimal_workers]
        
        for task in tasks_to_schedule:
            if task.assigned_machine:
                continue
            
            machine = self.select_machine(task, snapshot)
            if machine:
                transaction.add_placement(task, machine.id, machine.version)
                machine.allocated_cpu += task.cpu_req
                machine.allocated_gpu += task.gpu_req
                machine.allocated_memory += task.memory_req
        
        return transaction if transaction.placements else None
    
    def _calculate_utilization(self, snapshot: CellState) -> Dict[str, float]:
        """Calculate current cluster utilization"""
        total_cpu = sum(m.cpu_cores for m in snapshot.machines.values())
        total_mem = sum(m.memory_gb for m in snapshot.machines.values())
        
        used_cpu = sum(m.allocated_cpu for m in snapshot.machines.values())
        used_mem = sum(m.allocated_memory for m in snapshot.machines.values())
        
        return {
            'cpu': used_cpu / total_cpu if total_cpu > 0 else 0,
            'memory': used_mem / total_mem if total_mem > 0 else 0
        }
    
    def _get_available_resources(self, snapshot: CellState) -> Dict[str, float]:
        """Get total available resources"""
        available_cpu = sum(m.available_cpu() for m in snapshot.machines.values())
        available_mem = sum(m.available_memory() for m in snapshot.machines.values())
        available_gpu = sum(m.available_gpu() for m in snapshot.machines.values())
        
        return {
            'cpu': available_cpu,
            'memory': available_mem,
            'gpu': available_gpu
        }
    
    def _calculate_optimal_workers(self, job: Job, available_resources: Dict,
                                   utilization: Dict) -> int:
        """Calculate optimal number of workers based on policy"""
        base_workers = len(job.tasks)
        
        if self.policy == 'max_parallelism':
            # Use as many resources as available
            if not job.tasks:
                return 0
            
            task = job.tasks[0]  # Assume uniform task requirements
            max_by_cpu = int(available_resources['cpu'] / task.cpu_req) if task.cpu_req > 0 else base_workers
            max_by_mem = int(available_resources['memory'] / task.memory_req) if task.memory_req > 0 else base_workers
            
            return min(max_by_cpu, max_by_mem, base_workers * 10)  # Cap at 10x
        
        elif self.policy == 'global_cap':
            # Only use idle resources if utilization is below target
            avg_util = (utilization['cpu'] + utilization['memory']) / 2
            
            if avg_util > self.target_utilization:
                return base_workers  # Don't scale up
            
            # Scale based on how much below target we are
            scale_factor = 1.0 + (self.target_utilization - avg_util) * 5
            return int(base_workers * scale_factor)
        
        elif self.policy == 'relative_job_size':
            # Limit scaling to max_scale_factor times original size
            if not job.tasks:
                return 0
            
            task = job.tasks[0]
            max_by_cpu = int(available_resources['cpu'] / task.cpu_req) if task.cpu_req > 0 else base_workers
            max_by_mem = int(available_resources['memory'] / task.memory_req) if task.memory_req > 0 else base_workers
            
            max_workers = min(max_by_cpu, max_by_mem)
            return min(max_workers, int(base_workers * self.max_scale_factor))
        
        return base_workers
    
    def _predict_speedup(self, job: Job, additional_workers: int) -> float:
        """
        Predict speedup from adding workers.
        Uses simple linear model - could be enhanced with historical data.
        """
        if job.id in self.job_history:
            # Use historical data for prediction
            history = self.job_history[job.id]
            base_time = history.get('avg_duration', 100.0)
            base_workers = history.get('avg_workers', len(job.tasks))
        else:
            # Estimate based on task count
            base_time = len(job.tasks) * 10.0  # Assume 10s per task
            base_workers = len(job.tasks)
        
        # Simple linear speedup model (idealized)
        total_workers = base_workers + additional_workers
        if total_workers == 0:
            return 1.0
        
        speedup = total_workers / base_workers
        
        # Diminishing returns after certain point
        if speedup > 4.0:
            speedup = 4.0 + (speedup - 4.0) * 0.5
        
        return speedup
    
    def select_machine(self, task: Task, snapshot: CellState) -> Optional[Machine]:
        """Select machine for MapReduce task - prefer data locality"""
        # Sort by available resources (prefer machines with more free resources)
        machines = sorted(
            snapshot.machines.values(),
            key=lambda m: (m.available_cpu(), m.available_memory()),
            reverse=True
        )
        
        for machine in machines:
            if machine.can_fit(task.cpu_req, task.gpu_req, task.memory_req):
                return machine
        
        return None
    
    def update_job_history(self, job_id: str, duration: float, workers: int):
        """Update historical performance data"""
        if job_id not in self.job_history:
            self.job_history[job_id] = {
                'count': 0,
                'total_duration': 0.0,
                'total_workers': 0
            }
        
        history = self.job_history[job_id]
        history['count'] += 1
        history['total_duration'] += duration
        history['total_workers'] += workers
        history['avg_duration'] = history['total_duration'] / history['count']
        history['avg_workers'] = history['total_workers'] / history['count']
