"""
Base Scheduler: Abstract scheduler interface
"""
from abc import ABC, abstractmethod
from typing import List, Optional
import time
from core.cell_state import CellState, Job, Task, Transaction, Machine


class BaseScheduler(ABC):
    """Abstract base class for all schedulers"""
    
    def __init__(self, scheduler_id: str, cell_state: CellState, 
                 decision_time_per_job: float = 0.1,
                 decision_time_per_task: float = 0.005):
        self.scheduler_id = scheduler_id
        self.cell_state = cell_state
        self.decision_time_per_job = decision_time_per_job
        self.decision_time_per_task = decision_time_per_task
        
        # Statistics
        self.jobs_scheduled = 0
        self.tasks_scheduled = 0
        self.conflicts_encountered = 0
        self.total_decision_time = 0.0
        self.busy_time = 0.0
        self.job_wait_times = []
    
    @abstractmethod
    def schedule_job(self, job: Job, snapshot: CellState) -> Optional[Transaction]:
        """
        Schedule a job using the provided cell state snapshot.
        Returns a Transaction if successful, None otherwise.
        """
        pass
    
    @abstractmethod
    def select_machine(self, task: Task, snapshot: CellState) -> Optional[Machine]:
        """Select the best machine for a task"""
        pass
    
    def attempt_schedule(self, job: Job, max_retries: int = 5, 
                        incremental: bool = True) -> bool:
        """
        Attempt to schedule a job with retry logic for conflicts.
        """
        start_time = time.time()
        
        for attempt in range(max_retries):
            # Get fresh snapshot
            snapshot = self.cell_state.get_snapshot()
            
            # Make scheduling decision
            decision_start = time.time()
            transaction = self.schedule_job(job, snapshot)
            decision_time = time.time() - decision_start
            self.total_decision_time += decision_time
            
            if not transaction or not transaction.placements:
                return False
            
            # Attempt to commit
            success, conflicts = self.cell_state.commit_transaction(
                transaction, incremental=incremental
            )
            
            if success:
                self.jobs_scheduled += 1
                self.tasks_scheduled += len(transaction.placements)
                self.busy_time += time.time() - start_time
                return True
            
            # Handle conflicts
            self.conflicts_encountered += len(conflicts)
            
            if not incremental:
                # Gang scheduling - retry entire job
                continue
            else:
                # Incremental - partial success is OK
                if len(conflicts) < len(transaction.placements):
                    self.jobs_scheduled += 1
                    self.tasks_scheduled += len(transaction.placements) - len(conflicts)
                    self.busy_time += time.time() - start_time
                    return True
        
        self.busy_time += time.time() - start_time
        return False
    
    def get_statistics(self) -> dict:
        """Return scheduler statistics"""
        avg_wait_time = (sum(self.job_wait_times) / len(self.job_wait_times) 
                        if self.job_wait_times else 0)
        
        return {
            'scheduler_id': self.scheduler_id,
            'jobs_scheduled': self.jobs_scheduled,
            'tasks_scheduled': self.tasks_scheduled,
            'conflicts': self.conflicts_encountered,
            'conflict_rate': (self.conflicts_encountered / self.tasks_scheduled 
                            if self.tasks_scheduled > 0 else 0),
            'total_decision_time': self.total_decision_time,
            'busy_time': self.busy_time,
            'avg_wait_time': avg_wait_time
        }


class FirstFitScheduler(BaseScheduler):
    """Simple first-fit scheduler for baseline comparison"""
    
    def schedule_job(self, job: Job, snapshot: CellState) -> Optional[Transaction]:
        transaction = Transaction(self.scheduler_id)
        
        # Simulate decision time
        time.sleep(self.decision_time_per_job + 
                  self.decision_time_per_task * len(job.tasks))
        
        for task in job.tasks:
            if task.assigned_machine:
                continue
            
            machine = self.select_machine(task, snapshot)
            if machine:
                transaction.add_placement(task, machine.id, machine.version)
                # Update local snapshot
                machine.allocated_cpu += task.cpu_req
                machine.allocated_gpu += task.gpu_req
                machine.allocated_memory += task.memory_req
        
        return transaction if transaction.placements else None
    
    def select_machine(self, task: Task, snapshot: CellState) -> Optional[Machine]:
        """Select first machine that fits"""
        for machine in snapshot.machines.values():
            if machine.can_fit(task.cpu_req, task.gpu_req, task.memory_req):
                return machine
        return None


class RandomScheduler(BaseScheduler):
    """Random placement scheduler"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        import random
        self.random = random.Random(42)
    
    def schedule_job(self, job: Job, snapshot: CellState) -> Optional[Transaction]:
        transaction = Transaction(self.scheduler_id)
        
        time.sleep(self.decision_time_per_job + 
                  self.decision_time_per_task * len(job.tasks))
        
        machines = list(snapshot.machines.values())
        self.random.shuffle(machines)
        
        for task in job.tasks:
            if task.assigned_machine:
                continue
            
            for machine in machines:
                if machine.can_fit(task.cpu_req, task.gpu_req, task.memory_req):
                    transaction.add_placement(task, machine.id, machine.version)
                    machine.allocated_cpu += task.cpu_req
                    machine.allocated_gpu += task.gpu_req
                    machine.allocated_memory += task.memory_req
                    break
        
        return transaction if transaction.placements else None
    
    def select_machine(self, task: Task, snapshot: CellState) -> Optional[Machine]:
        machines = list(snapshot.machines.values())
        self.random.shuffle(machines)
        for machine in machines:
            if machine.can_fit(task.cpu_req, task.gpu_req, task.memory_req):
                return machine
        return None
