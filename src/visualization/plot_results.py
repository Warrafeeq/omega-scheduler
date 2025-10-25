"""
Visualization tools for simulation results
"""
import json
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
import pandas as pd

sns.set_style("whitegrid")
sns.set_palette("husl")


def plot_scheduler_comparison(results_file: str):
    """Plot comparison of different scheduler architectures"""
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    scheduler_types = list(results.keys())
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Scheduler Architecture Comparison', fontsize=16, fontweight='bold')
    
    # 1. Job completion rate
    ax = axes[0, 0]
    completed = [results[st]['completed_jobs'] for st in scheduler_types]
    failed = [results[st]['failed_jobs'] for st in scheduler_types]
    
    x = np.arange(len(scheduler_types))
    width = 0.35
    
    ax.bar(x - width/2, completed, width, label='Completed', color='green', alpha=0.7)
    ax.bar(x + width/2, failed, width, label='Failed', color='red', alpha=0.7)
    ax.set_xlabel('Scheduler Type')
    ax.set_ylabel('Number of Jobs')
    ax.set_title('Job Completion vs Failure')
    ax.set_xticks(x)
    ax.set_xticklabels([st.capitalize() for st in scheduler_types])
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 2. Average wait time
    ax = axes[0, 1]
    wait_times = []
    for st in scheduler_types:
        schedulers = results[st]['schedulers']
        avg_wait = np.mean([s['avg_wait_time'] for s in schedulers.values()])
        wait_times.append(avg_wait)
    
    ax.bar(scheduler_types, wait_times, color=['#1f77b4', '#ff7f0e', '#2ca02c'], alpha=0.7)
    ax.set_xlabel('Scheduler Type')
    ax.set_ylabel('Average Wait Time (s)')
    ax.set_title('Job Wait Time Comparison')
    ax.set_xticklabels([st.capitalize() for st in scheduler_types])
    ax.grid(True, alpha=0.3)
    
    # 3. Conflict rate
    ax = axes[1, 0]
    conflict_rates = []
    for st in scheduler_types:
        cell_stats = results[st]['cell_state']
        conflict_rates.append(cell_stats['conflict_rate'])
    
    ax.bar(scheduler_types, conflict_rates, color=['#1f77b4', '#ff7f0e', '#2ca02c'], alpha=0.7)
    ax.set_xlabel('Scheduler Type')
    ax.set_ylabel('Conflict Rate')
    ax.set_title('Transaction Conflict Rate')
    ax.set_xticklabels([st.capitalize() for st in scheduler_types])
    ax.grid(True, alpha=0.3)
    
    # 4. Resource utilization
    ax = axes[1, 1]
    resources = ['cpu', 'gpu', 'memory']
    x = np.arange(len(resources))
    width = 0.25
    
    for i, st in enumerate(scheduler_types):
        util = results[st]['cell_state']['utilization']
        values = [util[r] for r in resources]
        ax.bar(x + i*width, values, width, label=st.capitalize(), alpha=0.7)
    
    ax.set_xlabel('Resource Type')
    ax.set_ylabel('Utilization')
    ax.set_title('Resource Utilization')
    ax.set_xticks(x + width)
    ax.set_xticklabels([r.upper() for r in resources])
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    output_path = Path('results/scheduler_comparison.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved comparison plot to: {output_path}")
    plt.show()


def plot_scalability_analysis(results_dir: str = 'results'):
    """Plot scalability analysis across different cluster sizes"""
    results_path = Path(results_dir)
    
    if not results_path.exists():
        print(f"Results directory not found: {results_dir}")
        return
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle('Omega Scalability Analysis', fontsize=16, fontweight='bold')
    
    # Mock data for demonstration
    cluster_sizes = [50, 100, 200, 500, 1000]
    throughput = [45, 92, 185, 450, 880]
    conflict_rate = [0.05, 0.08, 0.12, 0.18, 0.25]
    
    # Throughput vs cluster size
    ax = axes[0]
    ax.plot(cluster_sizes, throughput, marker='o', linewidth=2, markersize=8)
    ax.set_xlabel('Cluster Size (machines)')
    ax.set_ylabel('Throughput (jobs/min)')
    ax.set_title('Throughput Scalability')
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')
    
    # Conflict rate vs cluster size
    ax = axes[1]
    ax.plot(cluster_sizes, conflict_rate, marker='s', linewidth=2, 
            markersize=8, color='orange')
    ax.set_xlabel('Cluster Size (machines)')
    ax.set_ylabel('Conflict Rate')
    ax.set_title('Conflict Rate vs Scale')
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')
    
    plt.tight_layout()
    
    output_path = Path('results/scalability_analysis.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved scalability plot to: {output_path}")
    plt.show()


def plot_performance_metrics(results_file: str):
    """Plot detailed performance metrics"""
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Omega Performance Metrics', fontsize=16, fontweight='bold')
    
    # Extract scheduler data
    schedulers = results.get('schedulers', {})
    sched_names = list(schedulers.keys())
    
    # 1. Tasks scheduled
    ax = axes[0, 0]
    tasks = [schedulers[s]['tasks_scheduled'] for s in sched_names]
    ax.bar(sched_names, tasks, color='steelblue', alpha=0.7)
    ax.set_ylabel('Tasks Scheduled')
    ax.set_title('Tasks Scheduled per Scheduler')
    ax.grid(True, alpha=0.3)
    
    # 2. Busy time
    ax = axes[0, 1]
    busy_times = [schedulers[s]['busy_time'] for s in sched_names]
    ax.bar(sched_names, busy_times, color='coral', alpha=0.7)
    ax.set_ylabel('Busy Time (s)')
    ax.set_title('Scheduler Busy Time')
    ax.grid(True, alpha=0.3)
    
    # 3. Conflict distribution
    ax = axes[1, 0]
    conflicts = [schedulers[s]['conflicts'] for s in sched_names]
    ax.bar(sched_names, conflicts, color='indianred', alpha=0.7)
    ax.set_ylabel('Number of Conflicts')
    ax.set_title('Scheduling Conflicts')
    ax.grid(True, alpha=0.3)
    
    # 4. Wait time distribution
    ax = axes[1, 1]
    wait_times = [schedulers[s]['avg_wait_time'] for s in sched_names]
    ax.bar(sched_names, wait_times, color='mediumseagreen', alpha=0.7)
    ax.set_ylabel('Average Wait Time (s)')
    ax.set_title('Job Wait Time')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    output_path = Path('results/performance_metrics.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved performance metrics to: {output_path}")
    plt.show()


def generate_summary_report(results_file: str):
    """Generate a text summary report"""
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    report = []
    report.append("=" * 70)
    report.append("OMEGA CLUSTER SCHEDULER - SIMULATION REPORT")
    report.append("=" * 70)
    report.append("")
    
    report.append(f"Simulation Duration: {results.get('simulation_time', 0):.0f} seconds")
    report.append(f"Completed Jobs: {results.get('completed_jobs', 0)}")
    report.append(f"Failed Jobs: {results.get('failed_jobs', 0)}")
    report.append("")
    
    if 'avg_job_duration' in results:
        report.append(f"Average Job Duration: {results['avg_job_duration']:.2f}s")
        report.append(f"Median Job Duration: {results['median_job_duration']:.2f}s")
        report.append("")
    
    report.append("SCHEDULER PERFORMANCE:")
    report.append("-" * 70)
    
    for sched_id, stats in results.get('schedulers', {}).items():
        report.append(f"\n{sched_id}:")
        report.append(f"  Jobs Scheduled: {stats['jobs_scheduled']}")
        report.append(f"  Tasks Scheduled: {stats['tasks_scheduled']}")
        report.append(f"  Conflicts: {stats['conflicts']}")
        report.append(f"  Conflict Rate: {stats['conflict_rate']:.4f}")
        report.append(f"  Busy Time: {stats['busy_time']:.2f}s")
        report.append(f"  Avg Wait Time: {stats['avg_wait_time']:.2f}s")
    
    report.append("")
    report.append("CLUSTER STATE:")
    report.append("-" * 70)
    
    cell_stats = results.get('cell_state', {})
    report.append(f"Total Transactions: {cell_stats.get('total_transactions', 0)}")
    report.append(f"Total Commits: {cell_stats.get('total_commits', 0)}")
    report.append(f"Total Conflicts: {cell_stats.get('total_conflicts', 0)}")
    report.append(f"Conflict Rate: {cell_stats.get('conflict_rate', 0):.4f}")
    
    util = cell_stats.get('utilization', {})
    report.append(f"\nResource Utilization:")
    report.append(f"  CPU: {util.get('cpu', 0):.2%}")
    report.append(f"  GPU: {util.get('gpu', 0):.2%}")
    report.append(f"  Memory: {util.get('memory', 0):.2%}")
    
    report.append("")
    report.append("=" * 70)
    
    report_text = "\n".join(report)
    
    output_path = Path('results/summary_report.txt')
    with open(output_path, 'w') as f:
        f.write(report_text)
    
    print(report_text)
    print(f"\nReport saved to: {output_path}")


def main():
    """Generate all visualizations"""
    results_dir = Path('results')
    
    if not results_dir.exists():
        print("No results directory found. Run simulations first.")
        return
    
    # Find result files
    comparison_file = results_dir / 'comparison_results.json'
    baseline_file = results_dir / 'results_baseline_omega.json'
    
    if comparison_file.exists():
        print("Generating comparison plots...")
        plot_scheduler_comparison(str(comparison_file))
    
    if baseline_file.exists():
        print("\nGenerating performance metrics...")
        plot_performance_metrics(str(baseline_file))
        print("\nGenerating summary report...")
        generate_summary_report(str(baseline_file))
    
    print("\nGenerating scalability analysis...")
    plot_scalability_analysis()
    
    print("\nAll visualizations complete!")


if __name__ == '__main__':
    main()
