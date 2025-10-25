"""
Unit tests for CellState and optimistic concurrency control
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

import pytest
from core.cell_state import CellState, Machine, Task, Job, Transaction


def test_cell_state_initialization():
    """Test basic cell state initialization"""
    cell_state = CellState()
    assert len(cell_state.machines) == 0
    assert len(cell_state.jobs) == 0
    assert cell_state.version == 0


def test_add_machine():
    """Test adding machines to cell state"""
    cell_state = CellState()
    machine = Machine(id="m1", cpu_cores=8, gpu_count=0, memory_gb=16.0)
    cell_state.add_machine(machine)
    
    assert "m1" in cell_state.machines
    assert cell_state.machines["m1"].cpu_cores == 8


def test_machine_resource_availability():
    """Test machine resource availability calculations"""
    machine = Machine(id="m1", cpu_cores=8, gpu_count=2, memory_gb=16.0)
    
    assert machine.available_cpu() == 8
    assert machine.available_gpu() == 2
    assert machine.available_memory() == 16.0
    
    machine.allocated_cpu = 4
    machine.allocated_memory = 8.0
    
    assert machine.available_cpu() == 4
    assert machine.available_memory() == 8.0


def test_machine_can_fit():
    """Test machine capacity checking"""
    machine = Machine(id="m1", cpu_cores=8, gpu_count=0, memory_gb=16.0)
    
    assert machine.can_fit(4, 0, 8.0) == True
    assert machine.can_fit(10, 0, 8.0) == False
    assert machine.can_fit(4, 1, 8.0) == False


def test_transaction_commit_success():
    """Test successful transaction commit"""
    cell_state = CellState()
    machine = Machine(id="m1", cpu_cores=8, gpu_count=0, memory_gb=16.0)
    cell_state.add_machine(machine)
    
    task = Task(id="t1", job_id="j1", cpu_req=2, gpu_req=0, 
                memory_req=4.0, duration=100, priority=5)
    
    transaction = Transaction("scheduler1")
    transaction.add_placement(task, "m1", machine.version)
    
    success, conflicts = cell_state.commit_transaction(transaction)
    
    assert success == True
    assert len(conflicts) == 0
    assert cell_state.machines["m1"].allocated_cpu == 2
    assert cell_state.machines["m1"].allocated_memory == 4.0


def test_transaction_conflict_detection():
    """Test conflict detection in concurrent transactions"""
    cell_state = CellState()
    machine = Machine(id="m1", cpu_cores=8, gpu_count=0, memory_gb=16.0)
    cell_state.add_machine(machine)
    
    task1 = Task(id="t1", job_id="j1", cpu_req=6, gpu_req=0,
                 memory_req=10.0, duration=100, priority=5)
    task2 = Task(id="t2", job_id="j2", cpu_req=6, gpu_req=0,
                 memory_req=10.0, duration=100, priority=5)
    
    # First transaction
    trans1 = Transaction("scheduler1")
    trans1.add_placement(task1, "m1", machine.version)
    success1, _ = cell_state.commit_transaction(trans1)
    assert success1 == True
    
    # Second transaction with stale version
    trans2 = Transaction("scheduler2")
    trans2.add_placement(task2, "m1", machine.version)  # Stale version
    success2, conflicts = cell_state.commit_transaction(trans2)
    
    assert success2 == False
    assert len(conflicts) > 0


def test_incremental_transaction():
    """Test incremental transaction with partial conflicts"""
    cell_state = CellState()
    m1 = Machine(id="m1", cpu_cores=8, gpu_count=0, memory_gb=16.0)
    m2 = Machine(id="m2", cpu_cores=8, gpu_count=0, memory_gb=16.0)
    cell_state.add_machine(m1)
    cell_state.add_machine(m2)
    
    # Pre-allocate m1
    task0 = Task(id="t0", job_id="j0", cpu_req=6, gpu_req=0,
                 memory_req=10.0, duration=100, priority=5)
    trans0 = Transaction("scheduler0")
    trans0.add_placement(task0, "m1", m1.version)
    cell_state.commit_transaction(trans0)
    
    # Try to place on both machines
    task1 = Task(id="t1", job_id="j1", cpu_req=4, gpu_req=0,
                 memory_req=8.0, duration=100, priority=5)
    task2 = Task(id="t2", job_id="j1", cpu_req=4, gpu_req=0,
                 memory_req=8.0, duration=100, priority=5)
    
    trans1 = Transaction("scheduler1")
    trans1.add_placement(task1, "m1", m1.version)  # Will conflict
    trans1.add_placement(task2, "m2", m2.version)  # Will succeed
    
    success, conflicts = cell_state.commit_transaction(trans1, incremental=True)
    
    # Should partially succeed
    assert "t1" in conflicts
    assert cell_state.machines["m2"].allocated_cpu == 4


def test_resource_release():
    """Test releasing resources when task completes"""
    cell_state = CellState()
    machine = Machine(id="m1", cpu_cores=8, gpu_count=0, memory_gb=16.0)
    cell_state.add_machine(machine)
    
    task = Task(id="t1", job_id="j1", cpu_req=4, gpu_req=0,
                memory_req=8.0, duration=100, priority=5)
    cell_state.tasks["t1"] = task
    
    transaction = Transaction("scheduler1")
    transaction.add_placement(task, "m1", machine.version)
    cell_state.commit_transaction(transaction)
    
    assert cell_state.machines["m1"].allocated_cpu == 4
    
    cell_state.release_task("t1")
    
    assert cell_state.machines["m1"].allocated_cpu == 0
    assert cell_state.machines["m1"].allocated_memory == 0.0


def test_utilization_calculation():
    """Test cluster utilization calculation"""
    cell_state = CellState()
    m1 = Machine(id="m1", cpu_cores=8, gpu_count=0, memory_gb=16.0)
    m2 = Machine(id="m2", cpu_cores=8, gpu_count=0, memory_gb=16.0)
    cell_state.add_machine(m1)
    cell_state.add_machine(m2)
    
    # Allocate 50% of resources
    m1.allocated_cpu = 4
    m1.allocated_memory = 8.0
    m2.allocated_cpu = 4
    m2.allocated_memory = 8.0
    
    util = cell_state.get_utilization()
    
    assert util['cpu'] == 0.5
    assert util['memory'] == 0.5


def test_statistics():
    """Test statistics collection"""
    cell_state = CellState()
    machine = Machine(id="m1", cpu_cores=8, gpu_count=0, memory_gb=16.0)
    cell_state.add_machine(machine)
    
    task = Task(id="t1", job_id="j1", cpu_req=2, gpu_req=0,
                memory_req=4.0, duration=100, priority=5)
    
    transaction = Transaction("scheduler1")
    transaction.add_placement(task, "m1", machine.version)
    cell_state.commit_transaction(transaction)
    
    stats = cell_state.get_statistics()
    
    assert stats['total_transactions'] == 1
    assert stats['total_commits'] == 1
    assert stats['total_conflicts'] == 0
    assert stats['conflict_rate'] == 0.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
