"""
Batch Scheduler: Fast, lightweight scheduler for short-lived batch jobs
"""
from typing import Optional
import time
from schedulers.base_scheduler import BaseScheduler
from core.cell_state import CellState, Job, Task, Transaction, Machine


class BatchScheduler(BaseScheduler):
    """
    Optimized scheduler for batch workloads.
    Uses fast heuristics and minimal decision time.
    """
    
    def __init__(self, scheduler_id: str, cell_state: CellState):
        # Fast decision times for batch jobs
        super().__init__(
            scheduler_id=scheduler_id,
            cell_state=cell_state,
            decision_time_per_job=0.01,  # 10ms per job
            decision_time_per_task=0.001  # 1ms per task
        )
        self.placement_strategy = 'best_fit'  # or 'first_fit', 'worst_fit'
    
    def schedule_job(self, job: Job, snapshot: CellState) -> Optional[Transaction]:
        """Schedule batch job with fast placement"""
        transaction = Transaction(self.scheduler_id)
        
        # Simulate fast decision time
        time.sleep(self.decision_time_per_job + 
                  self.decision_time_per_task * len(job.tasks))
        
        # Sort machines by available resources for better packing
        machines = sorted(
            snapshot.machines.values(),
            key=lambda m: (m.available_cpu(), m.available_memory())
        )
        
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
        """Select machine using best-fit strategy"""
        best_machine = None
        best_score = float('inf')
        
        for machine in snapshot.machines.values():
            if not machine.can_fit(task.cpu_req, task.gpu_req, task.memory_req):
                continue
            
            if self.placement_strategy == 'first_fit':
                return machine
            
            elif self.placement_strategy == 'best_fit':
                # Minimize wasted resources
                waste = (machine.available_cpu() - task.cpu_req +
                        machine.available_memory() - task.memory_req)
                if waste < best_score:
                    best_score = waste
                    best_machine = machine
            
            elif self.placement_strategy == 'worst_fit':
                # Maximize remaining resources (load balancing)
                remaining = (machine.available_cpu() + machine.available_memory())
                if remaining > best_score:
                    best_score = remaining
                    best_machine = machine
        
        return best_machine


class WeightedRoundRobinScheduler(BaseScheduler):
    """
    Weighted Round Robin scheduler for fair resource allocation
    """
    
    def __init__(self, scheduler_id: str, cell_state: CellState, weights: dict = None):
        super().__init__(
            scheduler_id=scheduler_id,
            cell_state=cell_state,
            decision_time_per_job=0.02,
            decision_time_per_task=0.002
        )
        self.weights = weights or {}
        self.current_index = 0
    
    def schedule_job(self, job: Job, snapshot: CellState) -> Optional[Transaction]:
        transaction = Transaction(self.scheduler_id)
        
        time.sleep(self.decision_time_per_job + 
                  self.decision_time_per_task * len(job.tasks))
        
        machines = list(snapshot.machines.values())
        weight = self.weights.get(job.job_type, 1.0)
        
        for task in job.tasks:
            if task.assigned_machine:
                continue
            
            # Round-robin with weight consideration
            attempts = 0
            while attempts < len(machines):
                machine = machines[self.current_index % len(machines)]
                self.current_index += 1
                attempts += 1
                
                if machine.can_fit(task.cpu_req, task.gpu_req, task.memory_req):
                    transaction.add_placement(task, machine.id, machine.version)
                    machine.allocated_cpu += task.cpu_req
                    machine.allocated_gpu += task.gpu_req
                    machine.allocated_memory += task.memory_req
                    break
        
        return transaction if transaction.placements else None
    
    def select_machine(self, task: Task, snapshot: CellState) -> Optional[Machine]:
        machines = list(snapshot.machines.values())
        for _ in range(len(machines)):
            machine = machines[self.current_index % len(machines)]
            self.current_index += 1
            if machine.can_fit(task.cpu_req, task.gpu_req, task.memory_req):
                return machine
        return None
