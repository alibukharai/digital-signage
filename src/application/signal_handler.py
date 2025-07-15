"""
Signal handling - Separated from orchestrator
"""

import asyncio
import signal
from typing import Callable, Optional

from ..interfaces import ILogger


class SignalHandler:
    """Handles OS signals for graceful shutdown"""

    def __init__(self, logger: ILogger):
        self.logger = logger
        self.shutdown_callback: Optional[Callable] = None
        self.signals_registered = False

    def register_shutdown_callback(self, callback: Callable) -> None:
        """Register callback for shutdown signal"""
        self.shutdown_callback = callback

    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown"""
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            self.signals_registered = True
            self.logger.info("Signal handlers registered")

        except Exception as e:
            self.logger.error(f"Failed to setup signal handlers: {e}")

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown")

        if self.shutdown_callback:
            try:
                # Create task for shutdown if we're in an event loop
                if asyncio.get_running_loop():
                    asyncio.create_task(self.shutdown_callback())
                else:
                    asyncio.run(self.shutdown_callback())
            except RuntimeError:
                # No event loop running, call directly if sync
                try:
                    if asyncio.iscoroutinefunction(self.shutdown_callback):
                        asyncio.run(self.shutdown_callback())
                    else:
                        self.shutdown_callback()
                except Exception as e:
                    self.logger.error(f"Error in shutdown callback: {e}")
        else:
            self.logger.warning("No shutdown callback registered")
