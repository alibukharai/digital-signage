"""
Main orchestrator for the provisioning system - Now follows SRP
"""

import asyncio
import signal
import sys
from typing import Any, Dict, Optional

from ..domain.configuration import ProvisioningConfig
from ..domain.events import EventBus, get_event_bus
from ..domain.state import ProvisioningEvent, ProvisioningStateMachine
from ..domain.validation import ValidationService
from ..interfaces import ILogger
from .background_task_manager import BackgroundTaskManager
from .dependency_injection import Container
from .provisioning_coordinator import ProvisioningCoordinator
from .service_manager import ServiceManager
from .signal_handler import SignalHandler
from .use_cases import (
    FactoryResetUseCase,
    NetworkProvisioningUseCase,
    OwnerSetupUseCase,
    SystemHealthUseCase,
)


class ProvisioningOrchestrator:
    """Main orchestrator - Now focused on coordination only"""

    def __init__(self, config: ProvisioningConfig, container: Container):
        self.config = config
        self.container = container
        self.logger = container.resolve(ILogger)

        # Separated components following SRP
        self.service_manager = ServiceManager(container, self.logger)
        self.task_manager = BackgroundTaskManager(self.logger)
        self.signal_handler = SignalHandler(self.logger)

        # Create domain services
        self.event_bus = get_event_bus()
        self.validation_service = ValidationService(self.logger)
        self.state_machine = ProvisioningStateMachine(self.event_bus, self.logger)

        # Create use cases
        self._create_use_cases()

        # Create coordinator
        self.coordinator = ProvisioningCoordinator(
            self.state_machine,
            self.event_bus,
            self.validation_service,
            self.network_provisioning,
            self.owner_setup,
            self.system_health,
            self.logger,
        )

        # Setup signal handling
        self.signal_handler.register_shutdown_callback(self.stop)
        self.signal_handler.setup_signal_handlers()

        self.logger.info("Provisioning orchestrator initialized")

    def _create_use_cases(self) -> None:
        """Create use cases with dependencies from container"""
        from ..interfaces import (
            IBluetoothService,
            IConfigurationService,
            IDisplayService,
            IFactoryResetService,
            IHealthMonitor,
            INetworkService,
            IOwnershipService,
            ISecurityService,
        )

        # Get services from container
        network_service = self.container.resolve(INetworkService)
        bluetooth_service = self.container.resolve(IBluetoothService)
        display_service = self.container.resolve(IDisplayService)
        security_service = self.container.resolve(ISecurityService)
        config_service = self.container.resolve(IConfigurationService)
        ownership_service = self.container.resolve(IOwnershipService)
        factory_reset_service = self.container.resolve(IFactoryResetService)
        health_monitor = self.container.resolve(IHealthMonitor)

        # Create use cases
        self.network_provisioning = NetworkProvisioningUseCase(
            network_service,
            bluetooth_service,
            display_service,
            security_service,
            config_service,
            self.validation_service,
            self.event_bus,
            self.state_machine,
            self.logger,
        )

        self.owner_setup = OwnerSetupUseCase(
            ownership_service,
            security_service,
            self.validation_service,
            self.event_bus,
            self.logger,
        )

        self.factory_reset = FactoryResetUseCase(
            factory_reset_service,
            ownership_service,
            config_service,
            self.event_bus,
            self.logger,
        )

        self.system_health = SystemHealthUseCase(
            health_monitor, self.event_bus, self.logger
        )

    async def start(self) -> bool:
        """Start the provisioning system"""
        try:
            self.logger.info("Starting Rock Pi 3399 provisioning system")

            # Start background services
            await self.service_manager.start_services()

            # Start provisioning coordination
            success = await self.coordinator.start_provisioning()

            if success:
                # Setup factory reset monitoring
                await self._setup_factory_reset_monitoring()

            return success

        except Exception as e:
            self.logger.error(f"Failed to start provisioning system: {e}")
            return False

    async def stop(self) -> None:
        """Stop the provisioning system"""
        try:
            self.logger.info("Stopping provisioning system")

            # Stop all background tasks
            await self.task_manager.stop_all_tasks()

            # Stop services
            await self.service_manager.stop_services()

            self.logger.info("Provisioning system stopped")

        except Exception as e:
            self.logger.error(f"Error stopping provisioning system: {e}")

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        try:
            return {
                "provisioning": self.coordinator.get_provisioning_status(),
                "tasks": self.task_manager.get_task_status(),
                "services": self.service_manager.is_running,
                "timestamp": asyncio.get_event_loop().time(),
            }
        except Exception as e:
            self.logger.error(f"Error getting system status: {e}")
            return {"error": str(e), "timestamp": asyncio.get_event_loop().time()}

    async def _setup_factory_reset_monitoring(self) -> None:
        """Setup factory reset monitoring as background task"""
        from ..domain.events import EventType

        try:
            # Subscribe to factory reset events
            self.event_bus.subscribe(
                EventType.FACTORY_RESET_TRIGGERED, self._on_factory_reset_triggered
            )

            # Start factory reset monitoring task with restart policy
            await self.task_manager.start_task(
                "factory_reset_monitor",
                self._monitor_factory_reset,
                restart_policy="always",  # Always restart if monitoring stops
                max_restarts=5,
                restart_delay=10.0,
                health_check_interval=60.0,  # Check every minute
            )

        except Exception as e:
            self.logger.error(f"Failed to setup factory reset monitoring: {e}")

    async def _monitor_factory_reset(self) -> None:
        """Monitor for factory reset trigger"""
        while True:
            try:
                # Check factory reset trigger
                if self.factory_reset.check_reset_trigger():
                    self.logger.info("Factory reset triggered")
                    await self.factory_reset.perform_reset()

                await asyncio.sleep(1)  # Check every second

            except asyncio.CancelledError:
                self.logger.info("Factory reset monitoring cancelled")
                break
            except Exception as e:
                self.logger.error(f"Factory reset monitoring error: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    def _on_factory_reset_triggered(self) -> None:
        """Handle factory reset trigger"""
        try:
            self.logger.info("Factory reset event received")
            asyncio.create_task(self.factory_reset.perform_reset())
        except Exception as e:
            self.logger.error(f"Error handling factory reset: {e}")


async def main() -> int:
    """Main entry point"""
    try:
        # Load configuration
        from ..domain.configuration_factory import ConfigurationFactory

        config_factory = ConfigurationFactory()
        config = config_factory.load_config()

        # Setup container with services using service registrar
        from .service_registrars import create_configured_container

        container = create_configured_container(config)

        # Create and run orchestrator
        orchestrator = ProvisioningOrchestrator(config, container)
        success = await orchestrator.start()

        if success:
            # Keep running until interrupted
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                pass

        await orchestrator.stop()
        return 0 if success else 1

    except Exception as e:
                        import logging
                logging.getLogger(__name__).critical(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
