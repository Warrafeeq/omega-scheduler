# Omega: Flexible, Scalable Schedulers for Large Compute Clusters

## Project Overview

This project implements a simulation-based prototype of the Omega cluster scheduler, demonstrating how it handles multi-tenant workloads, dependency-aware task graphs, and resource heterogeneity across large-scale compute clusters.

## Architecture

### Core Components

1. **Shared State Manager**: Maintains resilient cell state with optimistic concurrency control
2. **Scheduler Framework**: Supports multiple parallel schedulers with pluggable policies
3. **Resource Manager**: Handles heterogeneous resources (CPU, GPU, memory)
4. **Workload Generator**: Simulates realistic job arrival patterns and dependencies
5. **Conflict Resolution**: Implements transaction-based conflict detection and resolution

### Scheduler Types

- **Batch Scheduler**: Fast, lightweight scheduling for short-lived jobs
- **Service Scheduler**: Sophisticated placement for long-running, high-priority services
- **MapReduce Scheduler**: Opportunistic resource allocation for data-intensive jobs
- **Custom Schedulers**: Pluggable architecture for domain-specific policies

## Key Features

- **Optimistic Concurrency Control**: Lock-free scheduling with transaction-based updates
- **Multi-tenant Support**: Isolated schedulers with shared cluster visibility
- **Fault Tolerance**: Checkpoint/restart mechanisms and failure simulation
- **Scalability**: Horizontal scheduler scaling with load balancing
- **Flexibility**: Policy plug-ins for priority-based, fair-share, and dependency-aware scheduling

## Project Structure

```
Omega/
├── src/
│   ├── core/              # Core scheduling engine
│   ├── schedulers/        # Scheduler implementations
│   ├── resources/         # Resource management
│   ├── workload/          # Workload generation and traces
│   └── simulation/        # Discrete-event simulator
├── experiments/           # Experimental configurations
├── results/              # Output data and plots
├── docs/                 # Research documentation
└── tests/                # Unit and integration tests
```

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```bash
# Run basic simulation
python src/main.py --config experiments/baseline.yaml

# Run comparative experiments
python src/experiments/compare_schedulers.py

# Generate performance plots
python src/visualization/plot_results.py
```

## Evaluation Metrics

- **Throughput**: Jobs completed per unit time
- **Latency**: Job wait time and completion time
- **Fairness**: Resource allocation equity (DRF)
- **Utilization**: CPU, GPU, memory efficiency
- **Resilience**: Performance under failures and contention
- **Conflict Rate**: Transaction retry frequency

## Research Goals

1. Demonstrate Omega's scalability advantages over monolithic and two-level schedulers
2. Evaluate optimistic concurrency control effectiveness in production workloads
3. Show flexibility through specialized scheduler implementations
4. Measure fault tolerance and recovery capabilities

## References

Based on: Schwarzkopf, M., Konwinski, A., Abd-El-Malek, M., & Wilkes, J. (2013). 
"Omega: flexible, scalable schedulers for large compute clusters." EuroSys'13.
