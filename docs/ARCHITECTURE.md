# Omega Architecture Design

## Overview

Omega is a flexible, scalable cluster scheduler that uses **shared state** and **optimistic concurrency control** to enable parallel scheduling decisions across multiple independent schedulers.

## High-Level Architecture

```

                     Omega Architecture                       

                                                               
            
     Batch           Service        MapReduce         
    Scheduler       Scheduler       Scheduler         
            
                                                           
             Read Snapshot                                 
                       
                                                              
                                   
            Shared Cell State                               
           (Optimistic Locking)                             
                                   
                                                              
                                       
                                                             
                               
    Machines             Jobs                             
    Resources            Tasks                            
                               
                                                               

```

## Core Components

### 1. Cell State (Shared State Manager)

**Purpose**: Maintains the master copy of cluster resource allocations

**Key Features**:
- Thread-safe access to cluster state
- Version-based conflict detection
- Transaction log for auditing
- Resource utilization tracking

**Data Structures**:
- `machines`: Map of machine_id -> Machine objects
- `jobs`: Map of job_id -> Job objects
- `tasks`: Map of task_id -> Task objects
- `version`: Global state version counter

**Concurrency Control**:
```python
# Each machine has a version number
machine.version += 1  # Incremented on every change

# Transactions check versions before commit
if machine.version != expected_version:
    conflict_detected()
```

### 2. Scheduler Framework

**Base Scheduler Interface**:
```python
class BaseScheduler:
    def schedule_job(job, snapshot) -> Transaction
    def select_machine(task, snapshot) -> Machine
    def attempt_schedule(job, max_retries) -> bool
```

**Scheduler Types**:

#### Batch Scheduler
- **Decision Time**: 10ms per job + 1ms per task
- **Strategy**: Fast first-fit or best-fit placement
- **Use Case**: Short-lived, high-volume jobs

#### Service Scheduler
- **Decision Time**: 1s per job + 50ms per task
- **Strategy**: Sophisticated placement considering:
  - Failure domain diversity
  - Load balancing
  - Anti-affinity constraints
  - Resource scoring
- **Use Case**: Long-running, high-priority services

#### MapReduce Scheduler
- **Decision Time**: 200ms per job + 10ms per task
- **Strategy**: Opportunistic resource allocation
- **Policies**:
  - `max_parallelism`: Use all available resources
  - `global_cap`: Respect cluster utilization threshold
  - `relative_job_size`: Scale up to 4x original size
- **Use Case**: Data-intensive batch processing

### 3. Transaction Model

**Transaction Lifecycle**:

1. **Snapshot**: Scheduler gets consistent view of cell state
2. **Decision**: Scheduler makes placement decisions locally
3. **Commit**: Atomic update to shared state
4. **Conflict Detection**: Version checks on affected machines
5. **Resolution**: Incremental or all-or-nothing retry

**Conflict Detection Granularity**:

- **Fine-grained** (default): Per-machine version checking
- **Coarse-grained**: Any change to machine invalidates transaction

**Transaction Types**:

- **Incremental**: Accept partial placements (default)
- **Gang Scheduling**: All-or-nothing placement

### 4. Resource Model

**Resource Types**:
- CPU cores (integer)
- GPU devices (integer)
- Memory (float, GB)

**Machine Heterogeneity**:
- Standard: 8 CPU, 0 GPU, 16GB RAM (50%)
- High-CPU: 16 CPU, 0 GPU, 32GB RAM (30%)
- GPU: 8 CPU, 2 GPU, 32GB RAM (15%)
- Large: 32 CPU, 0 GPU, 128GB RAM (5%)

### 5. Workload Model

**Job Types**:

| Type    | Task Count | Duration  | CPU | Memory | Arrival Rate |
|---------|-----------|-----------|-----|--------|--------------|
| Batch   | 10±50     | 5min±10min| 2±1 | 4±2 GB | 10s          |
| Service | 5±10      | 24h±12h   | 4±2 | 8±4 GB | 60s          |

**Distributions**:
- Task count: Log-normal
- Duration: Log-normal
- Interarrival: Exponential (Poisson process)
- Resources: Normal

## Scheduling Policies

### Priority-Based Scheduling

```python
priority_levels = {
    'critical': 10,
    'high': 7-9,
    'normal': 4-6,
    'low': 1-3,
    'best_effort': 0
}
```

### Fair-Share (DRF)

Dominant Resource Fairness ensures equitable allocation across multiple resource types.

### Dependency-Aware

Support for DAG-structured jobs (e.g., MapReduce):
- Map stage -> Reduce stage dependencies
- Tasks scheduled respecting precedence constraints

## Fault Tolerance

### Failure Handling

1. **Machine Failures**:
   - Detected via heartbeat timeout
   - Tasks on failed machine released
   - Jobs rescheduled automatically

2. **Task Failures**:
   - Retry with exponential backoff
   - Configurable retry limits

3. **Scheduler Failures**:
   - Stateless schedulers can restart
   - Job queue persisted in cell state

### Checkpoint/Restart

- Cell state periodically checkpointed
- Transaction log for replay
- Scheduler state reconstructed from cell state

## Scalability Mechanisms

### Horizontal Scheduler Scaling

- Multiple batch schedulers with load balancing
- Hash-based job assignment
- Independent decision making

### Conflict Reduction Techniques

1. **Incremental Transactions**: Accept partial success
2. **Fine-grained Locking**: Per-machine version checks
3. **Backoff Strategies**: Exponential retry delays
4. **Resource Partitioning**: Soft limits per scheduler

### Performance Optimizations

- Snapshot caching with TTL
- Lazy state synchronization
- Batch transaction commits
- Parallel placement evaluation

## Comparison with Other Architectures

### Monolithic Scheduler

**Pros**:
- Simple implementation
- Global optimization
- Consistent policies

**Cons**:
- Head-of-line blocking
- Single point of contention
- Limited scalability

### Two-Level Scheduler (Mesos)

**Pros**:
- Parallel schedulers
- Framework isolation

**Cons**:
- Pessimistic locking
- Limited resource visibility
- Offer-based inefficiency

### Omega (Shared State)

**Pros**:
- Full resource visibility
- Optimistic concurrency
- No head-of-line blocking
- Flexible policies

**Cons**:
- Potential conflicts
- Wasted scheduling work
- Complexity in conflict resolution

## Key Design Decisions

1. **Optimistic vs Pessimistic Concurrency**
   - Chose optimistic for better parallelism
   - Conflicts are rare in practice (<10%)

2. **Incremental vs Gang Scheduling**
   - Default to incremental for better utilization
   - Gang scheduling opt-in per job

3. **Fine vs Coarse Conflict Detection**
   - Fine-grained reduces spurious conflicts
   - 2-3x better performance

4. **Centralized vs Distributed State**
   - Centralized for consistency
   - Replicated for fault tolerance

## Future Enhancements

1. **Predictive Scheduling**: ML-based placement optimization
2. **Dynamic Policy Adaptation**: Runtime policy switching
3. **Multi-Cell Federation**: Cross-cluster scheduling
4. **Advanced Preemption**: Priority-based task eviction
5. **Resource Overcommitment**: Statistical multiplexing
