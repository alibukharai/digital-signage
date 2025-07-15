"""
Provisioning workflow coordination - Core business logic
"""

import asyncio
from typing import Any, Dict, Optional

from ..domain.events import EventBus
from ..domain.state import ProvisioningEvent, ProvisioningStateMachine
from ..domain.validation import ValidationService
from ..interfaces import DeviceState, ILogger
from .use_cases import (
    NetworkProvisioningUseCase,
    OwnerSetupUseCase,
    SystemHealthUseCase,
)


class ProvisioningCoordinator:
    """Coordinates the provisioning workflow"""

    def __init__(
        self,
        state_machine: ProvisioningStateMachine,
        event_bus: EventBus,
        validation_service: ValidationService,
        network_provisioning: NetworkProvisioningUseCase,
        owner_setup: OwnerSetupUseCase,
        system_health: SystemHealthUseCase,
        logger: ILogger,
    ):
        self.state_machine = state_machine
        self.event_bus = event_bus
        self.validation_service = validation_service
        self.network_provisioning = network_provisioning
        self.owner_setup = owner_setup
        self.system_health = system_health
        self.logger = logger

    async def start_provisioning(self) -> bool:
        """Start the provisioning process"""
        try:
            self.logger.info("Starting provisioning coordinator")

            # Check if owner setup is required
            if not self.owner_setup.is_owner_registered():
                self.logger.info("Owner setup required")
                await self._handle_owner_setup()

            # Start network provisioning
            self.logger.info("Starting network provisioning")
            success = await self._handle_network_provisioning()

            if success:
                self.logger.info("Provisioning completed successfully")
                self.state_machine.handle_event(ProvisioningEvent.PROVISIONING_COMPLETE)
            else:
                self.logger.error("Provisioning failed")
                self.state_machine.handle_event(ProvisioningEvent.ERROR_OCCURRED)

            return success

        except Exception as e:
            self.logger.error(f"Provisioning coordinator error: {e}")
            self.state_machine.handle_event(ProvisioningEvent.ERROR_OCCURRED)
            return False

    async def _handle_owner_setup(self) -> None:
        """Handle owner setup process"""
        try:
            # Wait for owner setup with timeout
            timeout = 300  # 5 minutes
            elapsed = 0

            while elapsed < timeout and not self.owner_setup.is_owner_registered():
                await asyncio.sleep(1)
                elapsed += 1

            if self.owner_setup.is_owner_registered():
                self.logger.info("Owner setup completed")
                self.event_bus.publish("owner_setup_complete", {})
            else:
                self.logger.warning("Owner setup timed out")
                self.event_bus.publish("owner_setup_timeout", {})

        except Exception as e:
            self.logger.error(f"Owner setup error: {e}")

    async def _handle_network_provisioning(self) -> bool:
        """Handle network provisioning process"""
        try:
            # Wait for network provisioning with timeout
            timeout = 300  # 5 minutes
            elapsed = 0

            while elapsed < timeout and self.state_machine.get_current_state() not in [
                DeviceState.CONNECTED,
                DeviceState.ERROR,
            ]:
                await asyncio.sleep(1)
                elapsed += 1

            current_state = self.state_machine.get_current_state()

            if current_state == DeviceState.CONNECTED:
                self.logger.info("Network provisioning successful")
                return True
            elif elapsed >= timeout:
                self.logger.error("Network provisioning timed out")
                return False
            else:
                self.logger.error("Network provisioning failed")
                return False

        except Exception as e:
            self.logger.error(f"Network provisioning error: {e}")
            return False

    def get_provisioning_status(self) -> Dict[str, Any]:
        """Get current provisioning status"""
        return {
            "state": self.state_machine.get_current_state().value,
            "owner_registered": self.owner_setup.is_owner_registered(),
            "network_connected": self.state_machine.get_current_state()
            == DeviceState.CONNECTED,
            "system_health": self.system_health.get_system_status(),
        }
