"""
Test for BackgroundTaskManager integration with enhanced features
"""

import asyncio
from unittest.mock import Mock

import pytest

from src.application.background_task_manager import BackgroundTaskManager, TaskConfig


class MockLogger:
    def __init__(self):
        self.messages = []

    def info(self, msg):
        self.messages.append(("INFO", msg))

    def warning(self, msg):
        self.messages.append(("WARNING", msg))

    def error(self, msg):
        self.messages.append(("ERROR", msg))

    def debug(self, msg):
        self.messages.append(("DEBUG", msg))


@pytest.mark.asyncio
async def test_basic_task_management():
    """Test basic task management functionality"""
    logger = MockLogger()
    manager = BackgroundTaskManager(logger)

    # Test task that completes successfully
    async def simple_task():
        await asyncio.sleep(0.1)
        return "completed"

    # Start task
    success = await manager.start_task("test_task", simple_task)
    assert success

    # Wait for completion
    await asyncio.sleep(0.2)

    # Check status
    status = manager.get_task_status()
    assert "test_task" in status
    assert status["test_task"]["status"] == "completed"
    assert status["test_task"]["healthy"]

    # Cleanup
    await manager.stop_all_tasks()


@pytest.mark.asyncio
async def test_task_restart_policy():
    """Test automatic restart policies"""
    logger = MockLogger()
    manager = BackgroundTaskManager(logger)

    call_count = 0

    async def failing_task():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        if call_count < 3:  # Fail first 2 times
            raise Exception(f"Failure {call_count}")
        return "success"

    # Start task with restart policy
    success = await manager.start_task(
        "failing_task",
        failing_task,
        restart_policy="on_failure",
        max_restarts=3,
        restart_delay=0.1,
    )
    assert success

    # Wait for restarts
    await asyncio.sleep(1.0)

    # Check that task was restarted
    status = manager.get_task_status()
    if "failing_task" in status:
        assert status["failing_task"]["restart_count"] >= 1

    # Cleanup
    await manager.stop_all_tasks()


@pytest.mark.asyncio
async def test_task_timeout():
    """Test task execution timeout"""
    logger = MockLogger()
    manager = BackgroundTaskManager(logger)

    async def long_task():
        await asyncio.sleep(2.0)  # Will timeout
        return "completed"

    # Start task with short timeout
    success = await manager.start_task(
        "timeout_task", long_task, max_execution_time=0.5, restart_policy="never"
    )
    assert success

    # Wait for timeout
    await asyncio.sleep(1.0)

    # Check that task failed due to timeout
    metrics = manager.get_task_metrics("timeout_task")
    if metrics:
        assert metrics["total_failures"] > 0

    # Cleanup
    await manager.stop_all_tasks()


@pytest.mark.asyncio
async def test_health_monitoring():
    """Test health monitoring functionality"""
    logger = MockLogger()
    manager = BackgroundTaskManager(logger)

    async def healthy_task():
        # Run for a while to test monitoring
        for i in range(10):
            await asyncio.sleep(0.1)

    # Start task
    success = await manager.start_task("healthy_task", healthy_task)
    assert success

    # Wait for health monitoring to kick in
    await asyncio.sleep(0.5)

    # Check task health
    assert manager.is_task_healthy("healthy_task")

    # Get detailed metrics
    metrics = manager.get_task_metrics("healthy_task")
    assert metrics is not None
    assert metrics["is_healthy"]
    assert "uptime" in metrics

    # Cleanup
    await manager.stop_all_tasks()


@pytest.mark.asyncio
async def test_manual_restart():
    """Test manual task restart functionality"""
    logger = MockLogger()
    manager = BackgroundTaskManager(logger)

    call_count = 0

    async def countable_task():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.2)
        return f"run_{call_count}"

    # Start task
    success = await manager.start_task("countable_task", countable_task)
    assert success

    # Wait for completion
    await asyncio.sleep(0.3)
    assert call_count == 1

    # Manually restart
    restart_success = await manager.restart_task("countable_task")
    assert restart_success

    # Wait for restart completion
    await asyncio.sleep(0.3)
    assert call_count == 2

    # Cleanup
    await manager.stop_all_tasks()


if __name__ == "__main__":
    # Run tests individually for debugging
    asyncio.run(test_basic_task_management())
    print("✓ Basic task management test passed")

    asyncio.run(test_task_restart_policy())
    print("✓ Restart policy test passed")

    asyncio.run(test_task_timeout())
    print("✓ Timeout test passed")

    asyncio.run(test_health_monitoring())
    print("✓ Health monitoring test passed")

    asyncio.run(test_manual_restart())
    print("✓ Manual restart test passed")

    print("\n🎉 All BackgroundTaskManager tests passed!")
