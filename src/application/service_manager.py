"""
Service lifecycle management - Handles service startup/shutdown
"""

import asyncio
from typing import List, Optional

from ..interfaces import ILogger
from .dependency_injection import Container


class ServiceManager:
    """Manages service lifecycle and background tasks"""

    def __init__(self, container: Container, logger: ILogger):
        self.container = container
        self.logger = logger
        self.background_tasks: List[asyncio.Task] = []
        self.is_running = False

    async def start_services(self) -> bool:
        """Start all background services"""
        try:
            self.is_running = True

            # Start health monitoring
            from ..interfaces import IHealthMonitor

            health_monitor = self.container.try_resolve(IHealthMonitor)
            if health_monitor:
                task = asyncio.create_task(self._run_health_monitoring(health_monitor))
                self.background_tasks.append(task)

            self.logger.info("Background services started")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start services: {e}")
            return False

    async def stop_services(self) -> None:
        """Stop all background services"""
        try:
            self.is_running = False

            # Cancel all background tasks
            for task in self.background_tasks:
                if not task.done():
                    task.cancel()

            # Wait for tasks to complete
            if self.background_tasks:
                await asyncio.gather(*self.background_tasks, return_exceptions=True)

            self.background_tasks.clear()
            self.logger.info("Background services stopped")

        except Exception as e:
            self.logger.error(f"Error stopping services: {e}")

    async def _run_health_monitoring(self, health_monitor) -> None:
        """Background health monitoring task"""
        try:
            health_monitor.start_monitoring()

            while self.is_running:
                await asyncio.sleep(30)  # Check every 30 seconds

        except asyncio.CancelledError:
            self.logger.info("Health monitoring cancelled")
        except Exception as e:
            self.logger.error(f"Health monitoring error: {e}")
        finally:
            health_monitor.stop_monitoring()
