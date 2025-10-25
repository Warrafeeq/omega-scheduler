"""
Workload Generator: Creates realistic cluster workloads
"""
import random
import numpy as np
from typing import List, Dict
from core.cell_state import Job, Task


class WorkloadGenerator:
    """
    Generates synthetic workloads based on empirical distributions
    from production clusters.
    """
    
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.np_rng = np.random.RandomState(seed)
        
        # Distribution parameters from Google cluster traces
        self.batch_params = {
            'task_count_mean': 10,
            'task_count_std': 50,
            'duration_mean': 300,  # 5 minutes
            'duration_std': 600,
            'cpu_mean': 2,
            'cpu_std': 1,
            'memory_mean': 4.0,  # GB
            'memory_std': 2.0,
            'interarrival_mean': 10.0  # seconds
        }
        
        self.service_params = {
            'task_count_mean': 5,
            'task_count_std': 10,
            'duration_mean': 86400,  # 24 hours
            'duration_std': 43200,
            'cpu_mean': 4,
            'cpu_std': 2,
            'memory_mean': 8.0,
            'memory_std': 4.0,
            'interarrival_mean': 60.0
        }
    
    def generate_workload(self, duration: float, 
                         batch_ratio: float = 0.8) -> List[Job]:
        """
        Generate a workload for the specified duration.
        
        Args:
            duration: Simulation duration in seconds
            batch_ratio: Fraction of jobs that are batch jobs
        
        Returns:
            List of jobs with arrival times
        """
        jobs = []
        current_time = 0.0
        job_id = 0
        
        while current_time < duration:
            # Decide job type
            is_batch = self.rng.random() < batch_ratio
            job_type = 'batch' if is_batch else 'service'
            params = self.batch_params if is_batch else self.service_params
            
            # Generate job
            job = self._generate_job(
                job_id=f"job_{job_id}",
                job_type=job_type,
                submit_time=current_time,
                params=params
            )
            
            jobs.append(job)
            job_id += 1
            
            # Next arrival time (Poisson process)
            interarrival = self.np_rng.exponential(params['interarrival_mean'])
            current_time += interarrival
        
        return jobs
    
    def _generate_job(self, job_id: str, job_type: str, 
                     submit_time: float, params: Dict) -> Job:
        """Generate a single job"""
        # Number of tasks (log-normal distribution)
        task_count = max(1, int(self.np_rng.lognormal(
            np.log(params['task_count_mean']),
            np.log(params['task_count_std'] + 1)
        )))
        task_count = min(task_count, 1000)  # Cap at 1000 tasks
        
        # Generate tasks
        tasks = []
        for i in range(task_count):
            task = self._generate_task(
                task_id=f"{job_id}_task_{i}",
                job_id=job_id,
                params=params
            )
            tasks.append(task)
        
        # Job priority (higher for service jobs)
        priority = self.rng.randint(5, 10) if job_type == 'service' else self.rng.randint(1, 5)
        
        # Gang scheduling (rare, mostly for service jobs)
        gang_schedule = job_type == 'service' and self.rng.random() < 0.05
        
        return Job(
            id=job_id,
            tasks=tasks,
            job_type=job_type,
            submit_time=submit_time,
            priority=priority,
            gang_schedule=gang_schedule
        )
    
    def _generate_task(self, task_id: str, job_id: str, params: Dict) -> Task:
        """Generate a single task"""
        # Resource requirements
        cpu_req = max(1, int(self.np_rng.normal(
            params['cpu_mean'], params['cpu_std']
        )))
        
        memory_req = max(0.5, self.np_rng.normal(
            params['memory_mean'], params['memory_std']
        ))
        
        # GPU requirement (10% of tasks need GPU)
        gpu_req = 1 if self.rng.random() < 0.1 else 0
        
        # Task duration (log-normal)
        duration = max(1.0, self.np_rng.lognormal(
            np.log(params['duration_mean']),
            np.log(params['duration_std'] + 1)
        ))
        
        # Priority
        priority = self.rng.randint(1, 10)
        
        return Task(
            id=task_id,
            job_id=job_id,
            cpu_req=cpu_req,
            gpu_req=gpu_req,
            memory_req=memory_req,
            duration=duration,
            priority=priority
        )
    
    def generate_cluster(self, num_machines: int, 
                        heterogeneous: bool = True) -> List[Dict]:
        """
        Generate cluster configuration.
        
        Args:
            num_machines: Number of machines
            heterogeneous: Whether to create heterogeneous resources
        
        Returns:
            List of machine specifications
        """
        machines = []
        
        if heterogeneous:
            # Mix of machine types
            machine_types = [
                {'cpu': 8, 'gpu': 0, 'memory': 16.0, 'ratio': 0.5},   # Standard
                {'cpu': 16, 'gpu': 0, 'memory': 32.0, 'ratio': 0.3},  # High-CPU
                {'cpu': 8, 'gpu': 2, 'memory': 32.0, 'ratio': 0.15},  # GPU
                {'cpu': 32, 'gpu': 0, 'memory': 128.0, 'ratio': 0.05} # Large
            ]
        else:
            # Homogeneous cluster
            machine_types = [
                {'cpu': 8, 'gpu': 0, 'memory': 16.0, 'ratio': 1.0}
            ]
        
        for i in range(num_machines):
            # Select machine type based on ratios
            r = self.rng.random()
            cumulative = 0.0
            selected_type = machine_types[0]
            
            for mtype in machine_types:
                cumulative += mtype['ratio']
                if r <= cumulative:
                    selected_type = mtype
                    break
            
            machines.append({
                'id': f"machine_{i}",
                'cpu_cores': selected_type['cpu'],
                'gpu_count': selected_type['gpu'],
                'memory_gb': selected_type['memory']
            })
        
        return machines
    
    def generate_dag_job(self, job_id: str, submit_time: float,
                        num_stages: int = 3) -> Job:
        """
        Generate a job with task dependencies (DAG structure).
        Useful for MapReduce-style workloads.
        """
        tasks = []
        dependencies = []
        
        # Generate tasks in stages
        tasks_per_stage = [
            max(1, int(self.np_rng.lognormal(2, 1)))
            for _ in range(num_stages)
        ]
        
        stage_tasks = []
        for stage in range(num_stages):
            stage_task_list = []
            for i in range(tasks_per_stage[stage]):
                task_id = f"{job_id}_stage{stage}_task{i}"
                task = self._generate_task(
                    task_id=task_id,
                    job_id=job_id,
                    params=self.batch_params
                )
                tasks.append(task)
                stage_task_list.append(task_id)
            
            stage_tasks.append(stage_task_list)
        
        # Create dependencies between stages
        for stage in range(1, num_stages):
            for task_id in stage_tasks[stage]:
                # Depend on all tasks from previous stage
                dependencies.extend([
                    (prev_task, task_id) 
                    for prev_task in stage_tasks[stage - 1]
                ])
        
        job = Job(
            id=job_id,
            tasks=tasks,
            job_type='batch',
            submit_time=submit_time,
            priority=self.rng.randint(1, 5),
            dependencies=dependencies
        )
        
        return job
