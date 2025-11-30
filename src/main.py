"""
Main entry point for Omega cluster scheduler simulation
"""
import argparse
import yaml
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.cell_state import CellState, Machine
from schedulers.batch_scheduler import BatchScheduler, WeightedRoundRobinScheduler
from schedulers.service_scheduler import ServiceScheduler, PriorityScheduler
from schedulers.mapreduce_scheduler import MapReduceScheduler
from simulation.simulator import ClusterSimulator, FailureSimulator
from workload.workload_generator import WorkloadGenerator


def load_config(config_path: str) -> dict:
    # load the yaml config file
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def setup_cluster(config: dict) -> CellState:
    # setup the cluster with machines
    cell_state = CellState()
    # print("DEBUG: Setting up cluster...")  # TODO: remove this later
    
    # Generate or load cluster configuration
    workload_gen = WorkloadGenerator(seed=config.get('seed', 42))
    machines = workload_gen.generate_cluster(
        num_machines=config['cluster']['num_machines'],
        heterogeneous=config['cluster'].get('heterogeneous', True)
    )
    
    # Add machines to cell state
    for machine_spec in machines:
        machine = Machine(**machine_spec)
        cell_state.add_machine(machine)
    
    print(f"Initialized cluster with {len(machines)} machines")
    # FIXME: maybe add validation here to check if machines are valid?
    return cell_state


def setup_schedulers(config: dict, cell_state: CellState) -> list:
    """Initialize schedulers based on configuration"""
    schedulers = []
    
    for sched_config in config['schedulers']:
        sched_type = sched_config['type']
        sched_id = sched_config['id']
        
        if sched_type == 'batch':
            scheduler = BatchScheduler(sched_id, cell_state)
        elif sched_type == 'service':
            scheduler = ServiceScheduler(
                sched_id, cell_state,
                decision_time_per_job=sched_config.get('decision_time_job', 1.0),
                decision_time_per_task=sched_config.get('decision_time_task', 0.05)
            )
        elif sched_type == 'mapreduce':
            scheduler = MapReduceScheduler(
                sched_id, cell_state,
                policy=sched_config.get('policy', 'max_parallelism')
            )
        elif sched_type == 'priority':
            scheduler = PriorityScheduler(sched_id, cell_state)
        elif sched_type == 'weighted_rr':
            scheduler = WeightedRoundRobinScheduler(
                sched_id, cell_state,
                weights=sched_config.get('weights', {})
            )
        else:
            raise ValueError(f"Unknown scheduler type: {sched_type}")
        
        schedulers.append(scheduler)
        print(f"Initialized {sched_type} scheduler: {sched_id}")
    
    return schedulers


def generate_workload(config: dict, cell_state: CellState, schedulers: list):
    # generate jobs for the simulation
    workload_gen = WorkloadGenerator(seed=config.get('seed', 42))
    # print(f"DEBUG: workload_gen created with seed {config.get('seed', 42)}")
    
    # Generate jobs
    duration = config['simulation']['duration']
    batch_ratio = config['workload'].get('batch_ratio', 0.8)
    
    jobs = workload_gen.generate_workload(duration, batch_ratio)
    
    print(f"Generated {len(jobs)} jobs")
    
    # assign jobs to the right schedulers based on type
    scheduler_map = {s.scheduler_id: s for s in schedulers}
    job_assignments = []
    
    for job in jobs:
        # Route jobs to appropriate scheduler
        if job.job_type == 'batch':
            # Find batch scheduler
            batch_schedulers = [s for s in schedulers 
                              if isinstance(s, (BatchScheduler, WeightedRoundRobinScheduler))]
            if batch_schedulers:
                scheduler = batch_schedulers[0]
            else:
                scheduler = schedulers[0]
        else:
            # Find service scheduler
            service_schedulers = [s for s in schedulers 
                                if isinstance(s, (ServiceScheduler, PriorityScheduler))]
            if service_schedulers:
                scheduler = service_schedulers[0]
            else:
                scheduler = schedulers[0]
        
        job_assignments.append((job, scheduler.scheduler_id))
        cell_state.add_job(job)
    
    return job_assignments


def run_simulation(config: dict):
    """Run the complete simulation"""
    print("=" * 60)
    print("Omega Cluster Scheduler Simulation")
    print("=" * 60)
    
    # Setup
    cell_state = setup_cluster(config)
    schedulers = setup_schedulers(config, cell_state)
    job_assignments = generate_workload(config, cell_state, schedulers)
    
    # Create simulator
    sim_duration = config['simulation']['duration']
    simulator = ClusterSimulator(cell_state, schedulers, sim_duration)
    
    # Add job arrivals
    for job, scheduler_id in job_assignments:
        simulator.add_job_arrival(job, job.submit_time, scheduler_id)
    
    print(f"\nStarting simulation for {sim_duration} seconds...")
    
    # Run simulation
    results = simulator.run()
    
    # Print results
    print("\n" + "=" * 60)
    print("Simulation Results")
    print("=" * 60)
    
    print(f"\nCompleted jobs: {results['completed_jobs']}")
    print(f"Failed jobs: {results['failed_jobs']}")
    
    if 'avg_job_duration' in results:
        print(f"Average job duration: {results['avg_job_duration']:.2f}s")
        print(f"Median job duration: {results['median_job_duration']:.2f}s")
    
    print("\nScheduler Statistics:")
    for sched_id, stats in results['schedulers'].items():
        print(f"\n  {sched_id}:")
        print(f"    Jobs scheduled: {stats['jobs_scheduled']}")
        print(f"    Tasks scheduled: {stats['tasks_scheduled']}")
        print(f"    Conflicts: {stats['conflicts']}")
        print(f"    Conflict rate: {stats['conflict_rate']:.4f}")
        print(f"    Busy time: {stats['busy_time']:.2f}s")
        print(f"    Avg wait time: {stats['avg_wait_time']:.2f}s")
    
    print("\nCell State Statistics:")
    cell_stats = results['cell_state']
    print(f"  Total transactions: {cell_stats['total_transactions']}")
    print(f"  Total commits: {cell_stats['total_commits']}")
    print(f"  Total conflicts: {cell_stats['total_conflicts']}")
    print(f"  Conflict rate: {cell_stats['conflict_rate']:.4f}")
    
    util = cell_stats['utilization']
    print(f"\nFinal Utilization:")
    print(f"  CPU: {util['cpu']:.2%}")
    print(f"  GPU: {util['gpu']:.2%}")
    print(f"  Memory: {util['memory']:.2%}")
    
    # Save results
    output_dir = Path(config.get('output_dir', 'results'))
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / f"results_{config.get('experiment_name', 'default')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to: {output_file}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Omega Cluster Scheduler Simulator'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='experiments/baseline.yaml',
        help='Path to configuration file'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Run simulation
    run_simulation(config)


if __name__ == '__main__':
    main()
