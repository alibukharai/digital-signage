"""
Use cases for the provisioning system
"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from ..domain.errors import NetworkError, ProvisioningError, SecurityError
from ..domain.events import EventBus, EventType
from ..domain.state import ProvisioningEvent, ProvisioningStateMachine
from ..domain.validation import ValidationService
from ..interfaces import (
    ConnectionInfo,
    DeviceInfo,
    IBluetoothService,
    IConfigurationService,
    IDisplayService,
    IFactoryResetService,
    IHealthMonitor,
    ILogger,
    INetworkService,
    IOwnershipService,
    ISecurityService,
    NetworkInfo,
)


class NetworkProvisioningUseCase:
    """Use case for network provisioning workflow"""

    def __init__(
        self,
        network_service: INetworkService,
        bluetooth_service: IBluetoothService,
        display_service: IDisplayService,
        security_service: ISecurityService,
        config_service: IConfigurationService,
        validation_service: ValidationService,
        event_bus: EventBus,
        state_machine: ProvisioningStateMachine,
        logger: Optional[ILogger] = None,
    ):
        self.network_service = network_service
        self.bluetooth_service = bluetooth_service
        self.display_service = display_service
        self.security_service = security_service
        self.config_service = config_service
        self.validation_service = validation_service
        self.event_bus = event_bus
        self.state_machine = state_machine
        self.logger = logger

        # Set up BLE callback
        self.bluetooth_service.set_credentials_callback(self._on_credentials_received)

    async def start_provisioning(self, device_info: DeviceInfo) -> bool:
        """Start the network provisioning process"""
        try:
            if self.logger:
                self.logger.info("Starting network provisioning")

            # Check if already connected
            if self.network_service.is_connected():
                if self.logger:
                    self.logger.info("Already connected to network")
                return True

            # Check for saved configuration
            saved_config = self.config_service.load_network_config()
            if saved_config:
                ssid, password = saved_config
                if self.logger:
                    self.logger.info(f"Attempting connection with saved config: {ssid}")

                if self.network_service.connect_to_network(ssid, password):
                    if self.logger:
                        self.logger.info("Connected using saved configuration")
                    self.state_machine.process_event(
                        ProvisioningEvent.NETWORK_CONNECTED
                    )
                    return True

            # Start provisioning mode
            self.state_machine.process_event(ProvisioningEvent.START_PROVISIONING)

            # Generate QR code data
            qr_data = self._generate_qr_data(device_info)

            # Start display
            if not self.display_service.show_qr_code(qr_data):
                if self.logger:
                    self.logger.error("Failed to show QR code")
                return False

            # Start BLE advertising
            if not self.bluetooth_service.start_advertising(device_info):
                if self.logger:
                    self.logger.error("Failed to start BLE advertising")
                return False

            # Publish event
            self.event_bus.publish(
                EventType.PROVISIONING_STARTED,
                {"device_info": device_info, "qr_data": qr_data},
                "provisioning_use_case",
            )

            if self.logger:
                self.logger.info("Provisioning mode started successfully")

            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to start provisioning: {e}")
            self.state_machine.process_event(ProvisioningEvent.ERROR_OCCURRED, str(e))
            return False

    async def stop_provisioning(self) -> bool:
        """Stop the provisioning process"""
        try:
            if self.logger:
                self.logger.info("Stopping provisioning")

            # Stop BLE advertising
            self.bluetooth_service.stop_advertising()

            # Clear display
            self.display_service.clear_display()

            # Publish event
            self.event_bus.publish(
                EventType.PROVISIONING_COMPLETED,
                {"status": "stopped"},
                "provisioning_use_case",
            )

            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to stop provisioning: {e}")
            return False

    def get_network_scan(self) -> List[NetworkInfo]:
        """Get available networks"""
        try:
            networks = self.network_service.scan_networks()

            self.event_bus.publish(
                EventType.NETWORK_SCAN_COMPLETED,
                {"network_count": len(networks)},
                "provisioning_use_case",
            )

            return networks

        except Exception as e:
            if self.logger:
                self.logger.error(f"Network scan failed: {e}")
            return []

    def get_connection_status(self) -> ConnectionInfo:
        """Get current connection status"""
        return self.network_service.get_connection_info()

    def _on_credentials_received(self, ssid: str, password: str):
        """Handle received WiFi credentials"""
        try:
            if self.logger:
                self.logger.info(f"Credentials received for SSID: {ssid}")

            # Validate credentials
            is_valid, errors = self.validation_service.validate_wifi_credentials(
                ssid, password
            )
            if not is_valid:
                if self.logger:
                    self.logger.warning(f"Invalid credentials: {errors}")
                return

            # Additional security validation
            if not self.security_service.validate_credentials(ssid, password):
                if self.logger:
                    self.logger.warning("Security validation failed for credentials")
                return

            self.state_machine.process_event(
                ProvisioningEvent.CREDENTIALS_RECEIVED, {"ssid": ssid}
            )

            # Update display
            self.display_service.show_status("Connecting to network...")

            # Attempt connection
            if self.network_service.connect_to_network(ssid, password):
                # Save configuration
                self.config_service.save_network_config(ssid, password)

                # Update display
                self.display_service.show_status("Connected successfully!")

                # Publish success event
                self.event_bus.publish(
                    EventType.NETWORK_CONNECTION_SUCCESS,
                    {"ssid": ssid},
                    "provisioning_use_case",
                )

                self.state_machine.process_event(ProvisioningEvent.NETWORK_CONNECTED)

                if self.logger:
                    self.logger.info(f"Successfully connected to {ssid}")
            else:
                # Update display
                self.display_service.show_status("Connection failed. Please try again.")

                # Publish failure event
                self.event_bus.publish(
                    EventType.NETWORK_CONNECTION_FAILED,
                    {"ssid": ssid, "reason": "connection_timeout"},
                    "provisioning_use_case",
                )

                self.state_machine.process_event(ProvisioningEvent.CONNECTION_FAILED)

                if self.logger:
                    self.logger.error(f"Failed to connect to {ssid}")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error processing credentials: {e}")
            self.state_machine.process_event(ProvisioningEvent.ERROR_OCCURRED, str(e))

    def _generate_qr_data(self, device_info: DeviceInfo) -> str:
        """Generate QR code data"""
        return f"ROCKPI:{device_info.device_id}:{device_info.mac_address}"


class OwnerSetupUseCase:
    """Use case for device owner setup"""

    def __init__(
        self,
        ownership_service: IOwnershipService,
        security_service: ISecurityService,
        validation_service: ValidationService,
        event_bus: EventBus,
        logger: Optional[ILogger] = None,
    ):
        self.ownership_service = ownership_service
        self.security_service = security_service
        self.validation_service = validation_service
        self.event_bus = event_bus
        self.logger = logger

    def start_setup(self) -> bool:
        """Start owner setup mode"""
        try:
            if self.ownership_service.is_owner_registered():
                if self.logger:
                    self.logger.warning("Owner already registered")
                return False

            success = self.ownership_service.start_setup_mode()

            if success:
                self.event_bus.publish(
                    EventType.OWNER_SETUP_STARTED,
                    self.ownership_service.get_setup_info(),
                    "owner_setup_use_case",
                )

                if self.logger:
                    self.logger.info("Owner setup mode started")

            return success

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to start owner setup: {e}")
            return False

    def register_owner(self, pin: str, name: str) -> Tuple[bool, str]:
        """Register device owner"""
        try:
            # Validate PIN
            is_valid, errors = self.validation_service.validate_device_pin(pin)
            if not is_valid:
                return False, f"Invalid PIN: {', '.join(errors)}"

            # Validate name
            is_valid, errors = self.validation_service.validate_device_name(name)
            if not is_valid:
                return False, f"Invalid name: {', '.join(errors)}"

            # Register owner
            success, message = self.ownership_service.register_owner(pin, name)

            if success and self.logger:
                self.logger.info(f"Owner registered: {name}")

            return success, message

        except Exception as e:
            if self.logger:
                self.logger.error(f"Owner registration failed: {e}")
            return False, f"Registration error: {str(e)}"

    def authenticate_owner(self, pin: str) -> Tuple[bool, str]:
        """Authenticate existing owner"""
        try:
            success, message = self.ownership_service.authenticate_owner(pin)

            if success and self.logger:
                self.logger.info("Owner authentication successful")

            return success, message

        except Exception as e:
            if self.logger:
                self.logger.error(f"Owner authentication failed: {e}")
            return False, f"Authentication error: {str(e)}"

    def get_setup_info(self) -> Dict[str, Any]:
        """Get setup information"""
        return self.ownership_service.get_setup_info()

    def is_owner_registered(self) -> bool:
        """Check if owner is registered"""
        return self.ownership_service.is_owner_registered()


class FactoryResetUseCase:
    """Use case for factory reset operations"""

    def __init__(
        self,
        factory_reset_service: IFactoryResetService,
        ownership_service: IOwnershipService,
        config_service: IConfigurationService,
        event_bus: EventBus,
        logger: Optional[ILogger] = None,
    ):
        self.factory_reset_service = factory_reset_service
        self.ownership_service = ownership_service
        self.config_service = config_service
        self.event_bus = event_bus
        self.logger = logger

    def perform_reset(
        self, confirmation_code: str, owner_pin: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Perform factory reset"""
        try:
            # Validate owner PIN if provided
            if owner_pin:
                auth_success, auth_message = self.ownership_service.authenticate_owner(
                    owner_pin
                )
                if not auth_success:
                    return False, f"Owner authentication failed: {auth_message}"

            # Perform reset
            success, message = self.factory_reset_service.perform_reset(
                confirmation_code
            )

            if success:
                # Clear configuration
                self.config_service.clear_network_config()

                # Publish event
                self.event_bus.publish(
                    EventType.FACTORY_RESET_TRIGGERED,
                    {"confirmation_code": confirmation_code},
                    "factory_reset_use_case",
                )

                if self.logger:
                    self.logger.critical("Factory reset completed")

            return success, message

        except Exception as e:
            if self.logger:
                self.logger.error(f"Factory reset failed: {e}")
            return False, f"Reset error: {str(e)}"

    def get_reset_info(self) -> Dict[str, Any]:
        """Get factory reset information"""
        return self.factory_reset_service.get_reset_info()

    def is_reset_available(self) -> bool:
        """Check if factory reset is available"""
        return self.factory_reset_service.is_reset_available()


class SystemHealthUseCase:
    """Use case for system health monitoring"""

    def __init__(
        self,
        health_monitor: IHealthMonitor,
        event_bus: EventBus,
        logger: Optional[ILogger] = None,
    ):
        self.health_monitor = health_monitor
        self.event_bus = event_bus
        self.logger = logger

    def start_monitoring(self) -> bool:
        """Start health monitoring"""
        try:
            success = self.health_monitor.start_monitoring()

            if success and self.logger:
                self.logger.info("Health monitoring started")

            return success

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to start health monitoring: {e}")
            return False

    def stop_monitoring(self) -> bool:
        """Stop health monitoring"""
        try:
            success = self.health_monitor.stop_monitoring()

            if success and self.logger:
                self.logger.info("Health monitoring stopped")

            return success

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to stop health monitoring: {e}")
            return False

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        try:
            health_data = self.health_monitor.check_system_health()

            # Publish health check event
            self.event_bus.publish(
                EventType.SYSTEM_HEALTH_CHECK, health_data, "health_use_case"
            )

            return health_data

        except Exception as e:
            if self.logger:
                self.logger.error(f"Health check failed: {e}")
            return {"status": "error", "error": str(e)}

    def get_status_summary(self) -> str:
        """Get health status summary"""
        return self.health_monitor.get_health_status()
