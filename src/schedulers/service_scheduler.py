"""
Service Scheduler: Sophisticated scheduler for long-running service jobs
"""
from typing import Optional, List, Dict
import time
from schedulers.base_scheduler import BaseScheduler
from core.cell_state import CellState, Job, Task, Transaction, Machine


class ServiceScheduler(BaseScheduler):
    """
    Advanced scheduler for service workloads.
    Considers failure domains, load balancing, and sophisticated placement.
    """
    
    def __init__(self, scheduler_id: str, cell_state: CellState,
                 decision_time_per_job: float = 1.0,
                 decision_time_per_task: float = 0.05):
        super().__init__(
            scheduler_id=scheduler_id,
            cell_state=cell_state,
            decision_time_per_job=decision_time_per_job,
            decision_time_per_task=decision_time_per_task
        )
        self.failure_domains = {}  # machine_id -> domain_id
        self.anti_affinity_groups = {}  # job_id -> group_id
    
    def schedule_job(self, job: Job, snapshot: CellState) -> Optional[Transaction]:
        """Schedule service job with sophisticated placement"""
        transaction = Transaction(self.scheduler_id)
        
        # Simulate longer decision time for complex placement
        time.sleep(self.decision_time_per_job + 
                  self.decision_time_per_task * len(job.tasks))
        
        # Analyze cluster state for optimal placement
        machine_scores = self._score_machines(snapshot, job)
        
        # Sort machines by score (higher is better)
        sorted_machines = sorted(
            machine_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        placed_domains = set()
        
        for task in job.tasks:
            if task.assigned_machine:
                continue
            
            machine = self._select_machine_with_constraints(
                task, sorted_machines, placed_domains, snapshot
            )
            
            if machine:
                transaction.add_placement(task, machine.id, machine.version)
                machine.allocated_cpu += task.cpu_req
                machine.allocated_gpu += task.gpu_req
                machine.allocated_memory += task.memory_req
                
                # Track failure domain for anti-affinity
                domain = self.failure_domains.get(machine.id, machine.id)
                placed_domains.add(domain)
        
        return transaction if transaction.placements else None
    
    def _score_machines(self, snapshot: CellState, job: Job) -> Dict[str, float]:
        """Score machines based on multiple criteria"""
        scores = {}
        
        for machine_id, machine in snapshot.machines.items():
            score = 0.0
            
            # Resource availability (0-1)
            cpu_avail = machine.available_cpu() / machine.cpu_cores
            mem_avail = machine.available_memory() / machine.memory_gb
            score += (cpu_avail + mem_avail) / 2 * 100
            
            # Load balancing - prefer less loaded machines
            load = len(machine.tasks)
            score -= load * 5
            
            # Failure domain diversity
            domain = self.failure_domains.get(machine_id, machine_id)
            domain_count = sum(1 for m_id in snapshot.machines 
                             if self.failure_domains.get(m_id) == domain)
            score += (1.0 / domain_count) * 20 if domain_count > 0 else 0
            
            # Priority boost for machines with GPUs if needed
            if any(task.gpu_req > 0 for task in job.tasks):
                if machine.gpu_count > 0:
                    score += 50
            
            scores[machine_id] = score
        
        return scores
    
    def _select_machine_with_constraints(
        self, 
        task: Task, 
        sorted_machines: List[tuple],
        placed_domains: set,
        snapshot: CellState
    ) -> Optional[Machine]:
        """Select machine considering constraints and anti-affinity"""
        
        for machine_id, score in sorted_machines:
            machine = snapshot.machines[machine_id]
            
            if not machine.can_fit(task.cpu_req, task.gpu_req, task.memory_req):
                continue
            
            # Check constraints
            if task.constraints:
                if not self._check_constraints(task, machine):
                    continue
            
            # Anti-affinity: avoid placing in same failure domain
            domain = self.failure_domains.get(machine_id, machine_id)
            if domain in placed_domains and len(placed_domains) < len(snapshot.machines):
                # Try to find machine in different domain
                continue
            
            return machine
        
        # Fallback: relax anti-affinity if necessary
        for machine_id, score in sorted_machines:
            machine = snapshot.machines[machine_id]
            if machine.can_fit(task.cpu_req, task.gpu_req, task.memory_req):
                return machine
        
        return None
    
    def _check_constraints(self, task: Task, machine: Machine) -> bool:
        """Check if machine satisfies task constraints"""
        for constraint_type, constraint_value in task.constraints.items():
            if constraint_type == 'min_cpu':
                if machine.cpu_cores < constraint_value:
                    return False
            elif constraint_type == 'min_memory':
                if machine.memory_gb < constraint_value:
                    return False
            elif constraint_type == 'requires_gpu':
                if constraint_value and machine.gpu_count == 0:
                    return False
            elif constraint_type == 'machine_type':
                # Could check machine type/family
                pass
        
        return True
    
    def select_machine(self, task: Task, snapshot: CellState) -> Optional[Machine]:
        """Select best machine for a single task"""
        machine_scores = self._score_machines(snapshot, 
                                             Job(id='temp', tasks=[task], 
                                                 job_type='service', 
                                                 submit_time=0, priority=0))
        
        sorted_machines = sorted(
            machine_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for machine_id, _ in sorted_machines:
            machine = snapshot.machines[machine_id]
            if machine.can_fit(task.cpu_req, task.gpu_req, task.memory_req):
                if not task.constraints or self._check_constraints(task, machine):
                    return machine
        
        return None


class PriorityScheduler(BaseScheduler):
    """Priority-based scheduler with preemption support"""
    
    def __init__(self, scheduler_id: str, cell_state: CellState):
        super().__init__(
            scheduler_id=scheduler_id,
            cell_state=cell_state,
            decision_time_per_job=0.5,
            decision_time_per_task=0.01
        )
        self.preemption_enabled = True
    
    def schedule_job(self, job: Job, snapshot: CellState) -> Optional[Transaction]:
        transaction = Transaction(self.scheduler_id)
        
        time.sleep(self.decision_time_per_job + 
                  self.decision_time_per_task * len(job.tasks))
        
        for task in job.tasks:
            if task.assigned_machine:
                continue
            
            machine = self.select_machine(task, snapshot)
            if machine:
                transaction.add_placement(task, machine.id, machine.version)
                machine.allocated_cpu += task.cpu_req
                machine.allocated_gpu += task.gpu_req
                machine.allocated_memory += task.memory_req
            elif self.preemption_enabled:
                # Try to find machine with lower priority tasks
                machine = self._find_preemptable_machine(task, snapshot, job.priority)
                if machine:
                    transaction.add_placement(task, machine.id, machine.version)
        
        return transaction if transaction.placements else None
    
    def _find_preemptable_machine(self, task: Task, snapshot: CellState, 
                                  priority: int) -> Optional[Machine]:
        """Find machine where lower priority tasks can be preempted"""
        # Simplified preemption logic
        for machine in snapshot.machines.values():
            # Check if preempting would free enough resources
            # This is a simplified version - real implementation would be more complex
            if machine.cpu_cores >= task.cpu_req and machine.memory_gb >= task.memory_req:
                return machine
        return None
    
    def select_machine(self, task: Task, snapshot: CellState) -> Optional[Machine]:
        """Select machine with priority consideration"""
        for machine in sorted(snapshot.machines.values(), 
                            key=lambda m: m.available_cpu(), reverse=True):
            if machine.can_fit(task.cpu_req, task.gpu_req, task.memory_req):
                return machine
        return None
