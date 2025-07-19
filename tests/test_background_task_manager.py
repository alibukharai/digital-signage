#!/usr/bin/env python3
"""
Test script for enhanced BackgroundTaskManager
"""

import asyncio
import os
import sys
import time

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.application.background_task_manager import BackgroundTaskManager
from src.interfaces import ILogger


class TestLogger:
    """Simple test logger"""

    def info(self, msg):
        print(f"INFO: {msg}")

    def warning(self, msg):
        print(f"WARNING: {msg}")

    def error(self, msg):
        print(f"ERROR: {msg}")

    def debug(self, msg):
        print(f"DEBUG: {msg}")


async def test_task_normal():
    """Normal task that runs for a while"""
    print("Normal task started")
    for i in range(10):
        print(f"Normal task iteration {i}")
        await asyncio.sleep(1)
    print("Normal task completed")


async def test_task_failing():
    """Task that fails after a few iterations"""
    print("Failing task started")
    for i in range(3):
        print(f"Failing task iteration {i}")
        await asyncio.sleep(1)
    raise Exception("Simulated task failure")


async def test_task_timeout():
    """Task that runs too long and should timeout"""
    print("Long running task started")
    await asyncio.sleep(20)  # This will timeout
    print("Long running task completed")


async def main():
    """Test the enhanced BackgroundTaskManager"""
    logger = TestLogger()
    manager = BackgroundTaskManager(logger)

    print("=== Testing Enhanced BackgroundTaskManager ===")

    # Test 1: Normal task
    print("\n1. Starting normal task...")
    await manager.start_task("normal_task", test_task_normal, restart_policy="never")

    # Test 2: Failing task with restart
    print("\n2. Starting failing task with restart policy...")
    await manager.start_task(
        "failing_task",
        test_task_failing,
        restart_policy="on_failure",
        max_restarts=2,
        restart_delay=2.0,
    )

    # Test 3: Task with timeout
    print("\n3. Starting task with timeout...")
    await manager.start_task(
        "timeout_task",
        test_task_timeout,
        restart_policy="on_failure",
        max_execution_time=5.0,
        max_restarts=1,
    )

    # Monitor for a while
    print("\n4. Monitoring tasks...")
    for i in range(20):
        await asyncio.sleep(2)
        status = manager.get_task_status()
        print(f"\n--- Status Update {i+1} ---")
        for name, info in status.items():
            health = "✓" if info.get("healthy", False) else "✗"
            print(
                f"{name}: {info['status']} {health} (restarts: {info.get('restart_count', 0)})"
            )

    # Final status
    print("\n=== Final Status ===")
    status = manager.get_task_status()
    for name, info in status.items():
        print(f"\n{name}:")
        for key, value in info.items():
            if key != "config":
                print(f"  {key}: {value}")

    # Stop all tasks
    print("\n5. Stopping all tasks...")
    await manager.stop_all_tasks()
    print("Test completed!")


if __name__ == "__main__":
    asyncio.run(main())
