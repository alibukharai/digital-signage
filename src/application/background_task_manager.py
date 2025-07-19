"""
Background task management - Separated from orchestrator
Enhanced with health monitoring and automatic restart policies
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from ..interfaces import ILogger


@dataclass
class TaskConfig:
    """Configuration for background tasks"""

    name: str
    task_func: Callable
    args: tuple = ()
    kwargs: dict = None
    restart_policy: str = "on_failure"  # "never", "on_failure", "always"
    max_restarts: int = 3
    restart_delay: float = 5.0  # seconds
    health_check_interval: float = 30.0  # seconds
    max_execution_time: Optional[float] = None  # seconds, None for unlimited

    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}


@dataclass
class TaskMetrics:
    """Metrics for task monitoring"""

    start_time: datetime
    restart_count: int = 0
    last_restart_time: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    total_failures: int = 0
    is_healthy: bool = True
    execution_time: Optional[float] = None


class BackgroundTaskManager:
    """Manages background tasks and their lifecycle with health monitoring and restart policies"""

    def __init__(self, logger: ILogger):
        self.logger = logger
        self.tasks: Dict[str, asyncio.Task] = {}
        self.task_configs: Dict[str, TaskConfig] = {}
        self.task_metrics: Dict[str, TaskMetrics] = {}
        self.is_running = False
        self._health_monitor_task: Optional[asyncio.Task] = None
        
        # Add synchronization primitives to prevent race conditions
        self._task_lock = asyncio.Lock()  # Protects task dictionary operations
        self._metrics_lock = asyncio.Lock()  # Protects metrics updates
        self._state_lock = asyncio.Lock()  # Protects manager state changes
        
        # Add cancellation event for clean shutdown
        self._shutdown_event = asyncio.Event()

    async def start_task(
        self,
        name: str,
        task_func: Callable,
        *args,
        restart_policy: str = "on_failure",
        max_restarts: int = 3,
        restart_delay: float = 5.0,
        health_check_interval: float = 30.0,
        max_execution_time: Optional[float] = None,
        **kwargs,
    ) -> bool:
        """Start a named background task with enhanced configuration"""
        try:
            if name in self.tasks:
                self.logger.warning(f"Task {name} already running")
                return False

            # Create task configuration
            config = TaskConfig(
                name=name,
                task_func=task_func,
                args=args,
                kwargs=kwargs,
                restart_policy=restart_policy,
                max_restarts=max_restarts,
                restart_delay=restart_delay,
                health_check_interval=health_check_interval,
                max_execution_time=max_execution_time,
            )

            success = await self._start_task_with_config(config)
            if success:
                # Start health monitoring if not already running
                if not self._health_monitor_task:
                    self._health_monitor_task = asyncio.create_task(
                        self._health_monitoring_loop()
                    )

            return success

        except Exception as e:
            self.logger.error(f"Failed to start task {name}: {e}")
            return False

    async def _start_task_with_config(self, config: TaskConfig) -> bool:
        """Start a task with the given configuration with proper synchronization"""
        try:
            # Use locks to prevent race conditions during task creation
            async with self._task_lock:
                if config.name in self.tasks:
                    self.logger.warning(f"Task {config.name} already exists during creation")
                    return False
                
                # Create wrapper task for monitoring and restart capabilities
                task = asyncio.create_task(self._task_wrapper(config))
                task.set_name(config.name)

                self.tasks[config.name] = task
                self.task_configs[config.name] = config
                
            # Update metrics separately to avoid holding both locks
            async with self._metrics_lock:
                self.task_metrics[config.name] = TaskMetrics(start_time=datetime.now())

            self.logger.info(
                f"Started background task: {config.name} (restart_policy: {config.restart_policy})"
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to start task {config.name}: {e}")
            return False

    async def _task_wrapper(self, config: TaskConfig) -> None:
        """Wrapper for tasks that handles execution time limits and exception handling with improved timeout management"""
        metrics = self.task_metrics[config.name]
        task_start_time = time.time()

        try:
            start_time = time.time()

            if config.max_execution_time:
                # Run task with timeout and proper cancellation handling
                try:
                    await asyncio.wait_for(
                        config.task_func(*config.args, **config.kwargs),
                        timeout=config.max_execution_time,
                    )
                except asyncio.TimeoutError:
                    # Ensure task is properly cancelled
                    current_task = asyncio.current_task()
                    if current_task and not current_task.cancelled():
                        current_task.cancel()
                    raise
            else:
                # Run task without timeout but with cancellation support
                task = asyncio.create_task(
                    config.task_func(*config.args, **config.kwargs)
                )

                # Monitor for external cancellation requests
                while not task.done():
                    try:
                        await asyncio.wait_for(asyncio.shield(task), timeout=1.0)
                        break
                    except asyncio.TimeoutError:
                        # Check if we should continue running
                        if not self.is_running or config.name not in self.tasks:
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass
                            raise asyncio.CancelledError("Task cancelled externally")
                        continue

            # Task completed successfully
            execution_time = time.time() - start_time
            metrics.execution_time = execution_time
            metrics.is_healthy = True
            self.logger.info(
                f"Task {config.name} completed successfully in {execution_time:.2f}s"
            )

        except asyncio.TimeoutError:
            metrics.total_failures += 1
            metrics.is_healthy = False
            execution_time = time.time() - task_start_time
            self.logger.error(
                f"Task {config.name} timed out after {config.max_execution_time}s (actual: {execution_time:.2f}s)"
            )
            await self._handle_task_failure(config, "timeout")

        except asyncio.CancelledError:
            execution_time = time.time() - task_start_time
            self.logger.info(
                f"Task {config.name} was cancelled after {execution_time:.2f}s"
            )
            raise  # Re-raise to maintain cancellation semantics

        except Exception as e:
            metrics.total_failures += 1
            metrics.is_healthy = False
            execution_time = time.time() - task_start_time
            self.logger.error(
                f"Task {config.name} failed after {execution_time:.2f}s with exception: {e}"
            )
            await self._handle_task_failure(config, "exception")

    async def _handle_task_failure(self, config: TaskConfig, failure_type: str) -> None:
        """Handle task failures according to restart policy"""
        metrics = self.task_metrics[config.name]

        if config.restart_policy == "never":
            self.logger.info(f"Task {config.name} failed, restart policy is 'never'")
            return

        if config.restart_policy == "on_failure" and failure_type == "timeout":
            # Consider timeout as failure for restart
            pass
        elif config.restart_policy == "on_failure" and failure_type != "exception":
            return

        # Check if we've exceeded max restart attempts
        if metrics.restart_count >= config.max_restarts:
            self.logger.error(
                f"Task {config.name} exceeded max restarts ({config.max_restarts})"
            )
            return

        # Restart the task
        metrics.restart_count += 1
        metrics.last_restart_time = datetime.now()

        self.logger.info(
            f"Restarting task {config.name} (attempt {metrics.restart_count}/{config.max_restarts}) in {config.restart_delay}s"
        )

        # Wait for restart delay
        await asyncio.sleep(config.restart_delay)

        # Remove the failed task and start a new one
        if config.name in self.tasks:
            del self.tasks[config.name]

        # Start new task instance
        await self._start_task_with_config(config)

    async def stop_task(self, name: str) -> bool:
        """Stop a specific background task"""
        try:
            if name not in self.tasks:
                return True

            task = self.tasks[name]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Clean up task data
            del self.tasks[name]
            if name in self.task_configs:
                del self.task_configs[name]
            if name in self.task_metrics:
                del self.task_metrics[name]

            self.logger.info(f"Stopped background task: {name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to stop task {name}: {e}")
            return False

    async def stop_all_tasks(self) -> None:
        """Stop all background tasks"""
        try:
            # Stop health monitoring first
            if self._health_monitor_task and not self._health_monitor_task.done():
                self._health_monitor_task.cancel()
                try:
                    await self._health_monitor_task
                except asyncio.CancelledError:
                    pass
                self._health_monitor_task = None

            task_names = list(self.tasks.keys())
            for name in task_names:
                await self.stop_task(name)

            self.logger.info("All background tasks stopped")

        except Exception as e:
            self.logger.error(f"Error stopping tasks: {e}")

    async def _health_monitoring_loop(self) -> None:
        """Continuous health monitoring for all tasks with improved coordination"""
        try:
            self.logger.info("Starting health monitoring loop")

            while self.tasks:  # Continue while there are tasks to monitor
                await asyncio.sleep(5.0)  # Check every 5 seconds

                current_time = datetime.now()
                failed_tasks = []
                healthy_tasks = []

                # Collect health status for all tasks
                for name, task in list(self.tasks.items()):
                    try:
                        is_healthy = await self._check_task_health(
                            name, task, current_time
                        )
                        if is_healthy:
                            healthy_tasks.append(name)
                        else:
                            failed_tasks.append(name)
                    except Exception as e:
                        self.logger.error(f"Health check failed for task {name}: {e}")
                        failed_tasks.append(name)

                # Log periodic health summary
                if len(self.tasks) > 1:
                    self.logger.debug(
                        f"Health check summary: {len(healthy_tasks)} healthy, "
                        f"{len(failed_tasks)} failed out of {len(self.tasks)} total tasks"
                    )

                # Handle any failed health checks with coordination
                recovery_tasks = []
                for name in failed_tasks:
                    if name in self.task_configs:
                        config = self.task_configs[name]
                        # Create recovery task to avoid blocking the health monitor
                        recovery_task = asyncio.create_task(
                            self._handle_task_failure(config, "health_check_failure")
                        )
                        recovery_tasks.append(recovery_task)

                # Wait for recovery tasks to complete (with timeout)
                if recovery_tasks:
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*recovery_tasks, return_exceptions=True),
                            timeout=30.0,  # 30 second timeout for recovery operations
                        )
                    except asyncio.TimeoutError:
                        self.logger.warning("Some task recovery operations timed out")

        except asyncio.CancelledError:
            self.logger.info("Health monitoring loop cancelled")
        except Exception as e:
            self.logger.error(f"Health monitoring loop error: {e}")
        finally:
            self.logger.info("Health monitoring loop stopped")

    async def _check_task_health(
        self, name: str, task: asyncio.Task, current_time: datetime
    ) -> bool:
        """Check health of a specific task and return health status with proper synchronization"""
        # Use locks to prevent race conditions on shared state
        async with self._metrics_lock:
            if name not in self.task_metrics or name not in self.task_configs:
                return False

            metrics = self.task_metrics[name]
            config = self.task_configs[name]

            # Update last health check time atomically
            metrics.last_health_check = current_time

            # Check if task has completed unexpectedly
            if task.done():
                if task.cancelled():
                    self.logger.debug(f"Task {name} was cancelled")
                    metrics.is_healthy = False
                    return False
                elif task.exception():
                    exception = task.exception()
                    self.logger.warning(
                        f"Task {name} completed with exception: {exception}"
                    )
                    metrics.is_healthy = False
                    await self._handle_task_failure(config, "unexpected_completion")
                    return False
                else:
                    # Task completed normally
                    self.logger.info(f"Task {name} completed normally")
                    metrics.is_healthy = True
                    return True
            else:
                # Task is still running - check if it's been running too long
                if config.max_execution_time:
                    running_time = (current_time - metrics.start_time).total_seconds()
                    if running_time > config.max_execution_time * 1.2:  # 20% grace period
                        self.logger.warning(
                            f"Task {name} has been running for {running_time:.1f}s, "
                            f"exceeding max time {config.max_execution_time}s"
                        )
                        metrics.is_healthy = False
                        # Cancel the long-running task
                        task.cancel()
                        return False

                # Task is still running and healthy
                metrics.is_healthy = True
                return True

    def get_task_status(self) -> Dict[str, Any]:
        """Get detailed status of all tasks including health metrics"""
        status = {}
        current_time = datetime.now()

        for name, task in self.tasks.items():
            task_status = {
                "running": not task.done(),
                "healthy": True,
                "restart_count": 0,
                "total_failures": 0,
                "uptime": None,
                "last_restart": None,
                "execution_time": None,
            }

            if task.done():
                if task.cancelled():
                    task_status["status"] = "cancelled"
                    task_status["healthy"] = False
                elif task.exception():
                    task_status["status"] = "failed"
                    task_status["healthy"] = False
                    task_status["error"] = str(task.exception())
                else:
                    task_status["status"] = "completed"
            else:
                task_status["status"] = "running"

            # Add metrics if available
            if name in self.task_metrics:
                metrics = self.task_metrics[name]
                task_status.update(
                    {
                        "healthy": metrics.is_healthy,
                        "restart_count": metrics.restart_count,
                        "total_failures": metrics.total_failures,
                        "uptime": (current_time - metrics.start_time).total_seconds(),
                        "last_restart": metrics.last_restart_time.isoformat()
                        if metrics.last_restart_time
                        else None,
                        "execution_time": metrics.execution_time,
                    }
                )

            # Add configuration info
            if name in self.task_configs:
                config = self.task_configs[name]
                task_status["config"] = {
                    "restart_policy": config.restart_policy,
                    "max_restarts": config.max_restarts,
                    "restart_delay": config.restart_delay,
                    "max_execution_time": config.max_execution_time,
                }

            status[name] = task_status

        return status

    def get_task_metrics(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed metrics for a specific task"""
        if name not in self.task_metrics:
            return None

        metrics = self.task_metrics[name]
        current_time = datetime.now()

        return {
            "name": name,
            "start_time": metrics.start_time.isoformat(),
            "uptime": (current_time - metrics.start_time).total_seconds(),
            "restart_count": metrics.restart_count,
            "last_restart": metrics.last_restart_time.isoformat()
            if metrics.last_restart_time
            else None,
            "last_health_check": metrics.last_health_check.isoformat()
            if metrics.last_health_check
            else None,
            "total_failures": metrics.total_failures,
            "is_healthy": metrics.is_healthy,
            "execution_time": metrics.execution_time,
        }

    def is_task_healthy(self, name: str) -> bool:
        """Check if a specific task is healthy"""
        if name not in self.task_metrics:
            return False
        return self.task_metrics[name].is_healthy

    async def restart_task(self, name: str) -> bool:
        """Manually restart a specific task"""
        try:
            if name not in self.task_configs:
                self.logger.error(
                    f"Cannot restart task {name}: configuration not found"
                )
                return False

            config = self.task_configs[name]
            metrics = self.task_metrics.get(name)

            # Stop the current task
            await self.stop_task(name)

            # Reset restart count for manual restart
            if metrics:
                metrics.restart_count = 0
                metrics.total_failures = 0
                metrics.is_healthy = True

            # Start the task again
            return await self._start_task_with_config(config)

        except Exception as e:
            self.logger.error(f"Failed to restart task {name}: {e}")
            return False

    async def start(self) -> None:
        """Start the background task manager"""
        self.is_running = True
        self.logger.info("Background task manager started")

    async def stop(self) -> None:
        """Stop the background task manager and cleanup all resources"""
        try:
            self.is_running = False
            self.logger.info("Stopping background task manager...")

            # Stop all tasks with proper cleanup
            await self.stop_all_tasks()

            self.logger.info("Background task manager stopped")

        except Exception as e:
            self.logger.error(f"Error stopping background task manager: {e}")

    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup"""
        await self.stop()

    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall health summary of the task manager"""
        total_tasks = len(self.tasks)
        healthy_tasks = sum(
            1 for metrics in self.task_metrics.values() if metrics.is_healthy
        )
        failed_tasks = total_tasks - healthy_tasks

        total_failures = sum(
            metrics.total_failures for metrics in self.task_metrics.values()
        )
        total_restarts = sum(
            metrics.restart_count for metrics in self.task_metrics.values()
        )

        return {
            "total_tasks": total_tasks,
            "healthy_tasks": healthy_tasks,
            "failed_tasks": failed_tasks,
            "total_failures": total_failures,
            "total_restarts": total_restarts,
            "health_monitor_running": self._health_monitor_task is not None
            and not self._health_monitor_task.done(),
            "manager_running": self.is_running,
        }
