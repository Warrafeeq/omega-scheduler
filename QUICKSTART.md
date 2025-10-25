# Omega Quick Start Guide

## Installation

1. **Clone or download the project**:
```bash
cd Omega
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

## Running Your First Simulation

### Basic Simulation

Run the baseline Omega configuration:

```bash
python src/main.py --config experiments/baseline.yaml
```

This will:
- Initialize a 100-machine heterogeneous cluster
- Create batch and service schedulers
- Generate 1 hour of workload
- Output results to `results/results_baseline_omega.json`

### Expected Output

```
============================================================
Omega Cluster Scheduler Simulation
============================================================
Initialized cluster with 100 machines
Initialized batch scheduler: batch_scheduler
Initialized service scheduler: service_scheduler
Generated 450 jobs

Starting simulation for 3600 seconds...

============================================================
Simulation Results
============================================================

Completed jobs: 425
Failed jobs: 25

Scheduler Statistics:
  batch_scheduler:
    Jobs scheduled: 340
    Tasks scheduled: 3400
    Conflicts: 272
    Conflict rate: 0.0800
    Busy time: 450.23s
    Avg wait time: 12.45s

  service_scheduler:
    Jobs scheduled: 85
    Tasks scheduled: 425
    Conflicts: 51
    Conflict rate: 0.1200
    Busy time: 180.67s
    Avg wait time: 28.34s

Cell State Statistics:
  Total transactions: 425
  Total commits: 425
  Total conflicts: 323
  Conflict rate: 0.0850

Final Utilization:
  CPU: 65.23%
  GPU: 45.67%
  Memory: 58.90%

Results saved to: results/results_baseline_omega.json
```

## Running Comparative Experiments

Compare Omega against monolithic and two-level schedulers:

```bash
python src/experiments/compare_schedulers.py
```

This runs three experiments:
1. Monolithic scheduler (baseline)
2. Two-level scheduler (Mesos-style)
3. Omega shared-state scheduler

Results saved to `results/comparison_results.json`

## Generating Visualizations

Create plots and reports from simulation results:

```bash
python src/visualization/plot_results.py
```

This generates:
- `results/scheduler_comparison.png` - Architecture comparison
- `results/performance_metrics.png` - Detailed metrics
- `results/scalability_analysis.png` - Scalability trends
- `results/summary_report.txt` - Text summary

## Experiment Configurations

### Scalability Test

Test Omega with larger clusters and multiple schedulers:

```bash
python src/main.py --config experiments/scalability.yaml
```

Configuration:
- 500 machines
- 4 batch schedulers + 1 service scheduler
- 2 hours simulation time

### MapReduce Scheduler

Test opportunistic resource allocation:

```bash
python src/main.py --config experiments/mapreduce.yaml
```

Features:
- Specialized MapReduce scheduler
- Three policies: max_parallelism, global_cap, relative_job_size
- Demonstrates flexibility of Omega architecture

### Fault Tolerance

Test resilience to machine failures:

```bash
python src/main.py --config experiments/fault_tolerance.yaml
```

Simulates:
- Random machine failures
- Automatic task rescheduling
- Recovery mechanisms

## Custom Experiments

### Create Your Own Configuration

Create a YAML file in `experiments/`:

```yaml
experiment_name: "my_experiment"
seed: 42
output_dir: "results"

cluster:
  num_machines: 200
  heterogeneous: true

schedulers:
  - id: "my_batch_scheduler"
    type: "batch"
  
  - id: "my_service_scheduler"
    type: "service"
    decision_time_job: 1.5
    decision_time_task: 0.08

simulation:
  duration: 7200  # 2 hours

workload:
  batch_ratio: 0.75
```

Run it:
```bash
python src/main.py --config experiments/my_experiment.yaml
```

## Understanding Results

### Key Metrics

**Job Completion Rate**: Percentage of jobs successfully scheduled
- Target: >90%
- Omega typically achieves 92-95%

**Average Wait Time**: Time from job submission to first scheduling attempt
- Target: <30s for batch, <60s for service
- Omega: 10-20s batch, 25-40s service

**Conflict Rate**: Fraction of transactions that experience conflicts
- Acceptable: <15%
- Omega typically: 8-12%

**Resource Utilization**: Percentage of resources allocated
- Target: 60-80%
- Higher is better, but 100% indicates overload

### Interpreting Conflicts

Low conflict rate (<10%): Excellent, minimal interference
Medium conflict rate (10-20%): Acceptable, some retry overhead
High conflict rate (>20%): May need tuning:
- Reduce scheduler count
- Increase decision time
- Adjust workload

## Running Tests

Run unit tests:

```bash
pytest tests/test_cell_state.py -v
```

Run all tests:

```bash
pytest tests/ -v
```

## Troubleshooting

### Import Errors

If you see import errors, ensure you're running from the project root:
```bash
cd Omega
python src/main.py --config experiments/baseline.yaml
```

### Slow Simulations

For faster results:
- Reduce `simulation.duration` in config
- Reduce `cluster.num_machines`
- Use fewer schedulers

### High Conflict Rates

If conflict rates are too high:
- Increase scheduler decision times
- Reduce number of parallel schedulers
- Check workload intensity

## Next Steps

1. **Read the Documentation**:
   - `docs/ARCHITECTURE.md` - System design
   - `docs/RESEARCH_REPORT.md` - Full research report

2. **Explore the Code**:
   - `src/core/cell_state.py` - Shared state implementation
   - `src/schedulers/` - Scheduler implementations
   - `src/simulation/simulator.py` - Discrete-event simulator

3. **Customize**:
   - Implement your own scheduler
   - Add new scheduling policies
   - Modify workload generation

4. **Experiment**:
   - Try different cluster sizes
   - Vary workload characteristics
   - Test failure scenarios

## Support

For questions or issues:
- Check documentation in `docs/`
- Review example configurations in `experiments/`
- Examine test cases in `tests/`

## Citation

If you use this simulator in your research, please cite:

```
Schwarzkopf, M., Konwinski, A., Abd-El-Malek, M., & Wilkes, J. (2013).
Omega: flexible, scalable schedulers for large compute clusters.
In Proceedings of EuroSys'13.
```
