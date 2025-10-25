"""
Cell State: Shared cluster state with optimistic concurrency control
"""
import threading
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from copy import deepcopy
import time


@dataclass
class Machine:
    """Represents a physical machine in the cluster"""
    id: str
    cpu_cores: int
    gpu_count: int
    memory_gb: float
    allocated_cpu: int = 0
    allocated_gpu: int = 0
    allocated_memory: float = 0.0
    version: int = 0  # For optimistic concurrency control
    tasks: Set[str] = field(default_factory=set)
    
    def available_cpu(self) -> int:
        return self.cpu_cores - self.allocated_cpu
    
    def available_gpu(self) -> int:
        return self.gpu_count - self.allocated_gpu
    
    def available_memory(self) -> float:
        return self.memory_gb - self.allocated_memory
    
    def can_fit(self, cpu: int, gpu: int, memory: float) -> bool:
        return (self.available_cpu() >= cpu and 
                self.available_gpu() >= gpu and 
                self.available_memory() >= memory)


@dataclass
class Task:
    """Represents a task to be scheduled"""
    id: str
    job_id: str
    cpu_req: int
    gpu_req: int
    memory_req: float
    duration: float
    priority: int
    constraints: Dict = field(default_factory=dict)
    assigned_machine: Optional[str] = None


@dataclass
class Job:
    """Represents a job containing multiple tasks"""
    id: str
    tasks: List[Task]
    job_type: str  # 'batch' or 'service'
    submit_time: float
    priority: int
    dependencies: List[str] = field(default_factory=list)
    gang_schedule: bool = False


class Transaction:
    """Represents a scheduling transaction"""
    def __init__(self, scheduler_id: str):
        self.scheduler_id = scheduler_id
        self.placements: List[tuple] = []  # (task_id, machine_id)
        self.machine_versions: Dict[str, int] = {}
        self.timestamp = time.time()
    
    def add_placement(self, task: Task, machine_id: str, machine_version: int):
        self.placements.append((task, machine_id))
        self.machine_versions[machine_id] = machine_version


class CellState:
    """
    Shared cluster state with optimistic concurrency control.
    Maintains the master copy of resource allocations.
    """
    def __init__(self):
        self.machines: Dict[str, Machine] = {}
        self.jobs: Dict[str, Job] = {}
        self.tasks: Dict[str, Task] = {}
        self.lock = threading.RLock()
        self.version = 0
        self.transaction_log: List[Transaction] = []
        
        # Statistics
        self.total_commits = 0
        self.total_conflicts = 0
        self.total_transactions = 0
    
    def add_machine(self, machine: Machine):
        """Add a machine to the cluster"""
        with self.lock:
            self.machines[machine.id] = machine
    
    def add_job(self, job: Job):
        """Add a job to the system"""
        with self.lock:
            self.jobs[job.id] = job
            for task in job.tasks:
                self.tasks[task.id] = task
    
    def get_snapshot(self) -> 'CellState':
        """Return a consistent snapshot for a scheduler"""
        with self.lock:
            snapshot = CellState()
            snapshot.machines = deepcopy(self.machines)
            snapshot.jobs = deepcopy(self.jobs)
            snapshot.tasks = deepcopy(self.tasks)
            snapshot.version = self.version
            return snapshot
    
    def commit_transaction(self, transaction: Transaction, 
                          incremental: bool = True) -> tuple[bool, List[str]]:
        """
        Attempt to commit a transaction with conflict detection.
        Returns (success, list of conflicted tasks)
        """
        with self.lock:
            self.total_transactions += 1
            conflicts = []
            successful_placements = []
            
            # Check for conflicts (fine-grained)
            for task, machine_id in transaction.placements:
                machine = self.machines.get(machine_id)
                if not machine:
                    conflicts.append(task.id)
                    continue
                
                # Version-based conflict detection
                expected_version = transaction.machine_versions.get(machine_id)
                if expected_version is not None and machine.version != expected_version:
                    conflicts.append(task.id)
                    continue
                
                # Resource availability check
                if not machine.can_fit(task.cpu_req, task.gpu_req, task.memory_req):
                    conflicts.append(task.id)
                    continue
                
                successful_placements.append((task, machine_id))
            
            # Handle gang scheduling (all-or-nothing)
            if not incremental and conflicts:
                self.total_conflicts += len(transaction.placements)
                return False, [t.id for t, _ in transaction.placements]
            
            # Apply successful placements
            if successful_placements:
                for task, machine_id in successful_placements:
                    machine = self.machines[machine_id]
                    machine.allocated_cpu += task.cpu_req
                    machine.allocated_gpu += task.gpu_req
                    machine.allocated_memory += task.memory_req
                    machine.tasks.add(task.id)
                    machine.version += 1
                    
                    # Update task
                    self.tasks[task.id].assigned_machine = machine_id
                
                self.version += 1
                self.total_commits += 1
                self.transaction_log.append(transaction)
            
            if conflicts:
                self.total_conflicts += len(conflicts)
            
            return len(conflicts) == 0, conflicts
    
    def release_task(self, task_id: str):
        """Release resources held by a completed task"""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task or not task.assigned_machine:
                return
            
            machine = self.machines[task.assigned_machine]
            machine.allocated_cpu -= task.cpu_req
            machine.allocated_gpu -= task.gpu_req
            machine.allocated_memory -= task.memory_req
            machine.tasks.discard(task_id)
            machine.version += 1
            
            task.assigned_machine = None
    
    def get_utilization(self) -> Dict[str, float]:
        """Calculate cluster-wide resource utilization"""
        with self.lock:
            total_cpu = sum(m.cpu_cores for m in self.machines.values())
            total_gpu = sum(m.gpu_count for m in self.machines.values())
            total_mem = sum(m.memory_gb for m in self.machines.values())
            
            used_cpu = sum(m.allocated_cpu for m in self.machines.values())
            used_gpu = sum(m.allocated_gpu for m in self.machines.values())
            used_mem = sum(m.allocated_memory for m in self.machines.values())
            
            return {
                'cpu': used_cpu / total_cpu if total_cpu > 0 else 0,
                'gpu': used_gpu / total_gpu if total_gpu > 0 else 0,
                'memory': used_mem / total_mem if total_mem > 0 else 0
            }
    
    def get_statistics(self) -> Dict:
        """Return scheduling statistics"""
        with self.lock:
            conflict_rate = (self.total_conflicts / self.total_transactions 
                           if self.total_transactions > 0 else 0)
            return {
                'total_transactions': self.total_transactions,
                'total_commits': self.total_commits,
                'total_conflicts': self.total_conflicts,
                'conflict_rate': conflict_rate,
                'utilization': self.get_utilization()
            }
