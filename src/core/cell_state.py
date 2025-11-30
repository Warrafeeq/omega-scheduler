"""
Cell State: Shared cluster state with optimistic concurrency control

Ok so basically this is the heart of the whole system - it keeps track of
all machines and their resources. The tricky part here is handling multiple
schedulers trying to update stuff at the same time without locks (optimistic approach)

TODO: might wanna add some caching later if this gets slow
"""
import threading
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from copy import deepcopy
import time


@dataclass
class Machine:
    """Represents a physical machine in the cluster
    
    Each machine tracks its own resources and what tasks r running on it.
    The version number is super important for conflict detection - everytime
    we change something we bump this up
    """
    id: str
    cpu_cores: int
    gpu_count: int
    memory_gb: float
    allocated_cpu: int = 0
    allocated_gpu: int = 0
    allocated_memory: float = 0.0
    version: int = 0  # for optimistic concurrency - increment on every change
    tasks: Set[str] = field(default_factory=set)
    
    def available_cpu(self) -> int:
        # simple math to see whats left
        return self.cpu_cores - self.allocated_cpu
    
    def available_gpu(self) -> int:
        return self.gpu_count - self.allocated_gpu
    
    def available_memory(self) -> float:
        return self.memory_gb - self.allocated_memory
    
    def can_fit(self, cpu: int, gpu: int, memory: float) -> bool:
        # check if we got enough space for this task
        return (self.available_cpu() >= cpu and 
                self.available_gpu() >= gpu and 
                self.available_memory() >= memory)


@dataclass
class Task:
    """Represents a task to be scheduled
    
    Tasks are the actual work units that need to run somewhere.
    They know what resources they need and which machine theyre on (if any)
    """
    id: str
    job_id: str
    cpu_req: int
    gpu_req: int
    memory_req: float
    duration: float
    priority: int
    constraints: Dict = field(default_factory=dict)  # stuff like "needs GPU" etc
    assigned_machine: Optional[str] = None


@dataclass
class Job:
    """Represents a job containing multiple tasks
    
    Jobs can have dependencies between tasks and might need gang scheduling
    (all tasks start together or none at all)
    """
    id: str
    tasks: List[Task]
    job_type: str  # 'batch' or 'service'
    submit_time: float
    priority: int
    dependencies: List[str] = field(default_factory=list)
    gang_schedule: bool = False  # all-or-nothing placement


class Transaction:
    """Represents a scheduling transaction
    
    This is what schedulers create when they wanna place tasks.
    We track which machines we touched and their versions so we can
    detect conflicts later
    """
    def __init__(self, scheduler_id: str):
        self.scheduler_id = scheduler_id
        self.placements: List[tuple] = []  # (task_id, machine_id)
        self.machine_versions: Dict[str, int] = {}  # for conflict detection
        self.timestamp = time.time()
    
    def add_placement(self, task: Task, machine_id: str, machine_version: int):
        self.placements.append((task, machine_id))
        self.machine_versions[machine_id] = machine_version


class CellState:
    """
    Shared cluster state with optimistic concurrency control.
    
    This is where all the magic happens - multiple schedulers can read this
    at the same time and make decisions. When they try to commit changes,
    we check if anyone else modified the same machines in the meantime.
    
    The key insight: conflicts are rare in practice so optimistic approach works great!
    """
    def __init__(self):
        self.machines: Dict[str, Machine] = {}
        self.jobs: Dict[str, Job] = {}
        self.tasks: Dict[str, Task] = {}
        self.lock = threading.RLock()  # only for protecting internal data structures
        self.version = 0
        self.transaction_log: List[Transaction] = []
        
        # Stats for evaluation
        self.total_commits = 0
        self.total_conflicts = 0
        self.total_transactions = 0
    
    def add_machine(self, machine: Machine):
        """Add a machine to the cluster - pretty straightforward"""
        with self.lock:
            self.machines[machine.id] = machine
    
    def add_job(self, job: Job):
        """Register a new job in the system"""
        with self.lock:
            self.jobs[job.id] = job
            for task in job.tasks:
                self.tasks[task.id] = task
    
    def get_snapshot(self) -> 'CellState':
        """Return a consistent snapshot for a scheduler
        
        Schedulers work on snapshots so they dont block each other.
        This is kinda expensive (deep copy) but worth it for the parallelism
        """
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
        Try to commit a transaction - this is the critical part!
        
        We check if any machines changed since the scheduler made its decision.
        If yes -> conflict, scheduler needs to retry with fresh snapshot.
        If no -> apply changes and we're good
        
        incremental=True means we can commit partial success (some tasks placed)
        incremental=False means all-or-nothing (gang scheduling)
        """
        with self.lock:
            self.total_transactions += 1
            conflicts = []
            successful_placements = []
            
            # Check each placement for conflicts
            for task, machine_id in transaction.placements:
                machine = self.machines.get(machine_id)
                if not machine:
                    conflicts.append(task.id)
                    continue
                
                # Version check - did someone else modify this machine?
                expected_version = transaction.machine_versions.get(machine_id)
                if expected_version is not None and machine.version != expected_version:
                    conflicts.append(task.id)  # conflict detected!
                    continue
                
                # Double check resources are still available
                if not machine.can_fit(task.cpu_req, task.gpu_req, task.memory_req):
                    conflicts.append(task.id)
                    continue
                
                successful_placements.append((task, machine_id))
            
            # Gang scheduling - all or nothing
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
                    machine.version += 1  # bump version for next conflict check
                    
                    # Update task assignment
                    self.tasks[task.id].assigned_machine = machine_id
                
                self.version += 1
                self.total_commits += 1
                self.transaction_log.append(transaction)
            
            if conflicts:
                self.total_conflicts += len(conflicts)
            
            return len(conflicts) == 0, conflicts
    
    def release_task(self, task_id: str):
        """Free up resources when a task finishes"""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task or not task.assigned_machine:
                return
            
            machine = self.machines[task.assigned_machine]
            machine.allocated_cpu -= task.cpu_req
            machine.allocated_gpu -= task.gpu_req
            machine.allocated_memory -= task.memory_req
            machine.tasks.discard(task_id)
            machine.version += 1  # version bump here too
            
            task.assigned_machine = None
    
    def get_utilization(self) -> Dict[str, float]:
        """Calculate how much of the cluster we're actually using"""
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
        """Get stats for evaluation - conflict rate is the key metric here"""
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
