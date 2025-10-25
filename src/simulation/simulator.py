"""
Discrete-Event Simulator for Omega cluster scheduler
"""
import simpy
from typing import List, Dict, Callable
import random
from core.cell_state import CellState, Job, Task, Machine
from schedulers.base_scheduler import BaseScheduler


class ClusterSimulator:
    """
    Discrete-event simulator for cluster scheduling.
    Uses SimPy for event-driven simulation.
    """
    
    def __init__(self, cell_state: CellState, schedulers: List[BaseScheduler],
                 simulation_time: float = 86400.0):  # 24 hours default
        self.env = simpy.Environment()
        self.cell_state = cell_state
        self.schedulers = {s.scheduler_id: s for s in schedulers}
        self.simulation_time = simulation_time
        
        # Job queues for each scheduler
        self.job_queues: Dict[str, List[Job]] = {
            s_id: [] for s_id in self.schedulers.keys()
        }
        
        # Statistics
        self.completed_jobs = []
        self.failed_jobs = []
        self.active_tasks = {}
        
        # Events
        self.job_arrival_events = []
        self.task_completion_events = []
    
    def add_job_arrival(self, job: Job, arrival_time: float, scheduler_id: str):
        """Schedule a job arrival event"""
        self.job_arrival_events.append((arrival_time, job, scheduler_id))
    
    def run(self):
        """Run the simulation"""
        # Sort job arrivals by time
        self.job_arrival_events.sort(key=lambda x: x[0])
        
        # Start scheduler processes
        for scheduler_id, scheduler in self.schedulers.items():
            self.env.process(self._scheduler_process(scheduler_id))
        
        # Start job arrival process
        self.env.process(self._job_arrival_process())
        
        # Start task completion process
        self.env.process(self._task_completion_process())
        
        # Run simulation
        self.env.run(until=self.simulation_time)
        
        return self._collect_results()
    
    def _job_arrival_process(self):
        """Process job arrivals"""
        for arrival_time, job, scheduler_id in self.job_arrival_events:
            # Wait until arrival time
            yield self.env.timeout(arrival_time - self.env.now)
            
            # Add job to appropriate scheduler queue
            self.job_queues[scheduler_id].append(job)
    
    def _scheduler_process(self, scheduler_id: str):
        """Process for a single scheduler"""
        scheduler = self.schedulers[scheduler_id]
        queue = self.job_queues[scheduler_id]
        
        while True:
            if queue:
                job = queue.pop(0)
                
                # Record wait time
                wait_time = self.env.now - job.submit_time
                scheduler.job_wait_times.append(wait_time)
                
                # Attempt to schedule
                success = scheduler.attempt_schedule(
                    job, 
                    max_retries=5,
                    incremental=not job.gang_schedule
                )
                
                if success:
                    # Start tasks
                    for task in job.tasks:
                        if task.assigned_machine:
                            self.active_tasks[task.id] = {
                                'task': task,
                                'start_time': self.env.now,
                                'job': job
                            }
                            # Schedule completion
                            self.env.process(self._task_process(task))
                else:
                    self.failed_jobs.append(job)
            else:
                # Wait a bit before checking queue again
                yield self.env.timeout(0.1)
    
    def _task_process(self, task: Task):
        """Process for a single task execution"""
        # Wait for task duration
        yield self.env.timeout(task.duration)
        
        # Task completed
        if task.id in self.active_tasks:
            task_info = self.active_tasks.pop(task.id)
            job = task_info['job']
            
            # Release resources
            self.cell_state.release_task(task.id)
            
            # Check if all tasks in job are complete
            all_complete = all(
                t.id not in self.active_tasks 
                for t in job.tasks
            )
            
            if all_complete and job not in self.completed_jobs:
                completion_time = self.env.now
                job_duration = completion_time - job.submit_time
                self.completed_jobs.append({
                    'job': job,
                    'completion_time': completion_time,
                    'duration': job_duration
                })
    
    def _task_completion_process(self):
        """Monitor and handle task completions"""
        while True:
            yield self.env.timeout(1.0)
            # Periodic cleanup and monitoring
    
    def _collect_results(self) -> Dict:
        """Collect simulation results"""
        results = {
            'simulation_time': self.simulation_time,
            'completed_jobs': len(self.completed_jobs),
            'failed_jobs': len(self.failed_jobs),
            'schedulers': {}
        }
        
        # Collect per-scheduler statistics
        for scheduler_id, scheduler in self.schedulers.items():
            results['schedulers'][scheduler_id] = scheduler.get_statistics()
        
        # Collect cell state statistics
        results['cell_state'] = self.cell_state.get_statistics()
        
        # Job completion statistics
        if self.completed_jobs:
            durations = [j['duration'] for j in self.completed_jobs]
            results['avg_job_duration'] = sum(durations) / len(durations)
            results['median_job_duration'] = sorted(durations)[len(durations) // 2]
        
        return results


class FailureSimulator:
    """Simulates machine failures and recovery"""
    
    def __init__(self, cell_state: CellState, failure_rate: float = 0.001):
        self.cell_state = cell_state
        self.failure_rate = failure_rate  # Failures per machine per hour
        self.failed_machines = set()
    
    def inject_failure(self, machine_id: str):
        """Simulate a machine failure"""
        if machine_id in self.cell_state.machines:
            machine = self.cell_state.machines[machine_id]
            self.failed_machines.add(machine_id)
            
            # Release all tasks on failed machine
            tasks_to_release = list(machine.tasks)
            for task_id in tasks_to_release:
                self.cell_state.release_task(task_id)
    
    def recover_machine(self, machine_id: str):
        """Simulate machine recovery"""
        if machine_id in self.failed_machines:
            self.failed_machines.discard(machine_id)
    
    def simulate_failures(self, env: simpy.Environment, duration: float):
        """Process to simulate random failures"""
        while True:
            # Wait for next failure
            time_to_failure = random.expovariate(
                self.failure_rate * len(self.cell_state.machines)
            )
            yield env.timeout(time_to_failure)
            
            # Select random machine to fail
            available_machines = [
                m_id for m_id in self.cell_state.machines.keys()
                if m_id not in self.failed_machines
            ]
            
            if available_machines:
                machine_id = random.choice(available_machines)
                self.inject_failure(machine_id)
                
                # Schedule recovery
                recovery_time = random.uniform(60, 600)  # 1-10 minutes
                env.process(self._recovery_process(env, machine_id, recovery_time))
    
    def _recovery_process(self, env: simpy.Environment, 
                         machine_id: str, recovery_time: float):
        """Process for machine recovery"""
        yield env.timeout(recovery_time)
        self.recover_machine(machine_id)
