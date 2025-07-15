"""
Test doubles for services following LSP and consistent error handling patterns.
These provide deterministic behavior for testing while maintaining interface compliance.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import Mock

from src.common.result_handling import Result
from src.interfaces import (
    ConnectionInfo,
    ConnectionStatus,
    DeviceInfo,
    IBluetoothService,
    IConfigurationService,
    IDeviceInfoProvider,
    IDisplayService,
    IFactoryResetService,
    IHealthMonitor,
    ILogger,
    INetworkService,
    IOwnershipService,
    ISecurityService,
    NetworkInfo,
)


class TestNetworkService(INetworkService):
    """Test implementation of network service with predictable behavior"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.is_connected_flag = False
        self.available_networks = [
            NetworkInfo(ssid="TestNetwork", signal_strength=-45, security_type="WPA2"),
            NetworkInfo(
                ssid="TestNetwork5G", signal_strength=-50, security_type="WPA3"
            ),
            NetworkInfo(ssid="OpenNetwork", signal_strength=-60, security_type="Open"),
        ]
        self.current_ssid: Optional[str] = None

    def scan_networks(self) -> Result[List[NetworkInfo], Exception]:
        """Test implementation - returns predefined networks"""
        if self.logger:
            self.logger.info("Test network scan completed")
        return Result.success(self.available_networks)

    def connect_to_network(self, ssid: str, password: str) -> Result[bool, Exception]:
        """Test implementation - simulates connection"""
        if not ssid:
            return Result.failure(Exception("SSID required"))

        # Find network in available list
        network = next((n for n in self.available_networks if n.ssid == ssid), None)
        if not network:
            return Result.failure(Exception(f"Network {ssid} not found"))

        self.is_connected_flag = True
        self.current_ssid = ssid

        if self.logger:
            self.logger.info(f"Test connected to {ssid}")

        return Result.success(True)

    def disconnect(self) -> Result[bool, Exception]:
        """Test implementation - simulates disconnection"""
        self.is_connected_flag = False
        self.current_ssid = None

        if self.logger:
            self.logger.info("Test disconnected")

        return Result.success(True)

    def get_connection_info(self) -> Result[ConnectionInfo, Exception]:
        """Test implementation - returns current connection info"""
        if self.is_connected_flag:
            return Result.success(
                ConnectionInfo(
                    status=ConnectionStatus.CONNECTED,
                    ssid=self.current_ssid,
                    ip_address="192.168.1.100",
                )
            )
        else:
            return Result.success(ConnectionInfo(status=ConnectionStatus.DISCONNECTED))

    def is_connected(self) -> bool:
        """Test implementation - returns connection status"""
        return self.is_connected_flag


class TestBluetoothService(IBluetoothService):
    """Test implementation of Bluetooth service with predictable behavior"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.is_advertising_flag = False
        self.credentials_callback: Optional[Callable[[str, str], None]] = None

    def start_advertising(self, device_info: DeviceInfo) -> Result[bool, Exception]:
        """Test implementation - simulates BLE advertising"""
        self.is_advertising_flag = True

        if self.logger:
            self.logger.info("Test BLE advertising started")

        return Result.success(True)

    def stop_advertising(self) -> Result[bool, Exception]:
        """Test implementation - simulates stopping BLE advertising"""
        self.is_advertising_flag = False

        if self.logger:
            self.logger.info("Test BLE advertising stopped")

        return Result.success(True)

    def is_advertising(self) -> bool:
        """Test implementation - returns advertising status"""
        return self.is_advertising_flag

    def set_credentials_callback(self, callback: Callable[[str, str], None]) -> None:
        """Test implementation - sets callback for credentials"""
        self.credentials_callback = callback
        if self.logger:
            self.logger.debug("Test credentials callback set")

    def simulate_credentials_received(self, ssid: str, password: str):
        """Test helper method to simulate receiving credentials"""
        if self.credentials_callback:
            self.credentials_callback(ssid, password)


class TestDisplayService(IDisplayService):
    """Test implementation of display service with predictable behavior"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.is_active = False
        self.last_qr_data: Optional[str] = None
        self.last_status_message: Optional[str] = None

    def show_qr_code(self, data: str) -> Result[bool, Exception]:
        """Test implementation - simulates QR code display"""
        self.last_qr_data = data
        self.is_active = True

        if self.logger:
            self.logger.info(f"Test QR code displayed: {data}")

        return Result.success(True)

    def show_status(self, message: str) -> Result[bool, Exception]:
        """Test implementation - simulates status display"""
        self.last_status_message = message

        if self.logger:
            self.logger.info(f"Test status displayed: {message}")

        return Result.success(True)

    def clear_display(self) -> Result[bool, Exception]:
        """Test implementation - simulates clearing display"""
        self.is_active = False
        self.last_qr_data = None
        self.last_status_message = None

        if self.logger:
            self.logger.info("Test display cleared")

        return Result.success(True)

    def is_display_active(self) -> bool:
        """Test implementation - returns display status"""
        return self.is_active


class TestConfigurationService(IConfigurationService):
    """Test implementation of configuration service with predictable behavior"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.stored_config: Optional[Tuple[str, str]] = None

    def save_network_config(self, ssid: str, password: str) -> Result[bool, Exception]:
        """Test implementation - stores config in memory"""
        if not ssid or not password:
            return Result.failure(Exception("SSID and password required"))

        self.stored_config = (ssid, password)

        if self.logger:
            self.logger.info(f"Test config saved: {ssid}")

        return Result.success(True)

    def load_network_config(self) -> Result[Optional[Tuple[str, str]], Exception]:
        """Test implementation - returns stored config"""
        if self.logger:
            self.logger.info("Test config loaded")

        return Result.success(self.stored_config)

    def clear_network_config(self) -> Result[bool, Exception]:
        """Test implementation - clears stored config"""
        had_config = self.stored_config is not None
        self.stored_config = None

        if self.logger:
            self.logger.info("Test config cleared")

        return Result.success(had_config)

    def has_network_config(self) -> bool:
        """Test implementation - returns whether config exists"""
        return self.stored_config is not None


class TestLogger(ILogger):
    """Test implementation of logger that stores log messages"""

    def __init__(self):
        self.messages = []

    def debug(self, message: str, **kwargs) -> None:
        self.messages.append(("DEBUG", message, kwargs))

    def info(self, message: str, **kwargs) -> None:
        self.messages.append(("INFO", message, kwargs))

    def warning(self, message: str, **kwargs) -> None:
        self.messages.append(("WARNING", message, kwargs))

    def error(self, message: str, **kwargs) -> None:
        self.messages.append(("ERROR", message, kwargs))

    def critical(self, message: str, **kwargs) -> None:
        self.messages.append(("CRITICAL", message, kwargs))

    def get_messages(self) -> List[Tuple[str, str, dict]]:
        """Get all logged messages"""
        return self.messages.copy()

    def clear_messages(self) -> None:
        """Clear all logged messages"""
        self.messages.clear()


class TestSecurityService(ISecurityService):
    """Test implementation of security service with predictable behavior"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        # SECURITY: Removed encryption_enabled - encryption is always mandatory in tests
        self.sessions = {}

    def encrypt_data(
        self, data: str, key_id: Optional[str] = None
    ) -> Result[bytes, Exception]:
        """Test implementation - simulates encryption (ALWAYS ENABLED)"""
        # SECURITY: No encryption bypass allowed even in tests

        # Simple test encryption - always applied
        encrypted = f"ENCRYPTED:{data}".encode("utf-8")

        if self.logger:
            self.logger.debug(f"Test data encrypted")

        return Result.success(encrypted)

    def decrypt_data(
        self, encrypted_data: bytes, key_id: Optional[str] = None
    ) -> Result[str, Exception]:
        """Test implementation - simulates decryption (ALWAYS ENABLED)"""
        # SECURITY: No encryption bypass allowed even in tests

        # Simple test decryption - always applied
        data_str = encrypted_data.decode("utf-8")
        if data_str.startswith("ENCRYPTED:"):
            decrypted = data_str[10:]  # Remove "ENCRYPTED:" prefix
        else:
            decrypted = data_str

        if self.logger:
            self.logger.debug(f"Test data decrypted")

        return Result.success(decrypted)

    def validate_credentials(self, ssid: str, password: str) -> Result[bool, Exception]:
        """Test implementation - validates credentials"""
        # Basic test validation
        if not ssid or not password:
            return Result.success(False)

        if len(password) < 8:
            return Result.success(False)

        if self.logger:
            self.logger.debug(f"Test credentials validated: {ssid}")

        return Result.success(True)

    def create_session(self, client_id: str) -> Result[str, Exception]:
        """Test implementation - creates session"""
        session_id = f"test_session_{client_id}_{len(self.sessions)}"
        self.sessions[session_id] = {
            "client_id": client_id,
            "created_at": 1234567890,  # Fixed timestamp for testing
        }

        if self.logger:
            self.logger.info(f"Test session created: {session_id}")

        return Result.success(session_id)


class TestHealthMonitorService(IHealthMonitor):
    """Test implementation of health monitor service with predictable behavior"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.is_monitoring = False
        self.health_status = "healthy"

    def check_system_health(self) -> Result[Dict[str, Any], Exception]:
        """Test implementation - returns test health data"""
        health_data = {
            "timestamp": 1234567890,  # Fixed timestamp for testing
            "cpu": {"usage": 25.0, "temperature": 45.0},
            "memory": {"used": 512, "total": 2048, "usage_percent": 25.0},
            "disk": {"used": 1024, "total": 16384, "usage_percent": 6.25},
            "network": {"interface": "wlan0", "status": "connected"},
            "status": self.health_status,
        }

        if self.logger:
            self.logger.debug(f"Test health check completed: {self.health_status}")

        return Result.success(health_data)

    def start_monitoring(self) -> Result[bool, Exception]:
        """Test implementation - starts monitoring"""
        self.is_monitoring = True

        if self.logger:
            self.logger.info("Test monitoring started")

        return Result.success(True)

    def stop_monitoring(self) -> Result[bool, Exception]:
        """Test implementation - stops monitoring"""
        self.is_monitoring = False

        if self.logger:
            self.logger.info("Test monitoring stopped")

        return Result.success(True)

    def get_health_status(self) -> Result[str, Exception]:
        """Test implementation - returns health status"""
        return Result.success(self.health_status)

    def set_health_status(self, status: str):
        """Test helper method to set health status"""
        self.health_status = status


class TestOwnershipService(IOwnershipService):
    """Test implementation of ownership service with predictable behavior"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.owner_registered = False
        self.stored_pin_hash = None
        self.owner_name = None
        self.setup_mode_active = False

    def is_owner_registered(self) -> bool:
        """Test implementation - returns registration status"""
        return self.owner_registered

    def register_owner(self, pin: str, name: str) -> Result[bool, Exception]:
        """Test implementation - registers owner"""
        if not self.setup_mode_active:
            return Result.failure(Exception("Setup mode not active"))

        if not pin or len(pin) < 4:
            return Result.failure(Exception("Invalid PIN"))

        if not name or len(name.strip()) < 2:
            return Result.failure(Exception("Invalid name"))

        self.stored_pin_hash = f"hash_{pin}"  # Simple test hash
        self.owner_name = name
        self.owner_registered = True
        self.setup_mode_active = False

        if self.logger:
            self.logger.info(f"Test owner registered: {name}")

        return Result.success(True)

    def authenticate_owner(self, pin: str) -> Result[bool, Exception]:
        """Test implementation - authenticates owner"""
        if not self.owner_registered:
            return Result.failure(Exception("No owner registered"))

        expected_hash = f"hash_{pin}"
        if expected_hash == self.stored_pin_hash:
            if self.logger:
                self.logger.info("Test owner authentication successful")
            return Result.success(True)
        else:
            if self.logger:
                self.logger.warning("Test owner authentication failed")
            return Result.failure(Exception("Invalid PIN"))

    def start_setup_mode(self) -> Result[bool, Exception]:
        """Test implementation - starts setup mode"""
        if self.owner_registered:
            return Result.failure(Exception("Owner already registered"))

        self.setup_mode_active = True

        if self.logger:
            self.logger.info("Test setup mode started")

        return Result.success(True)

    def reset_for_testing(self):
        """Test helper method to reset state"""
        self.owner_registered = False
        self.stored_pin_hash = None
        self.owner_name = None
        self.setup_mode_active = False


class TestFactoryResetService(IFactoryResetService):
    """Test implementation of factory reset service with predictable behavior"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.reset_available = True
        self.recovery_mode = False
        self.last_reset_successful = True

    def is_reset_available(self) -> bool:
        """Test implementation - returns reset availability"""
        return self.reset_available

    def perform_reset(self, confirmation_code: str) -> Result[bool, Exception]:
        """Test implementation - performs reset"""
        if not self.recovery_mode:
            return Result.failure(Exception("Device not in recovery mode"))

        if confirmation_code != "TEST_RESET_CODE":
            return Result.failure(Exception("Invalid confirmation code"))

        if self.logger:
            self.logger.critical("Test factory reset performed")

        # Simulate reset success/failure based on test configuration
        if self.last_reset_successful:
            return Result.success(True)
        else:
            return Result.failure(Exception("Reset failed"))

    def get_reset_info(self) -> Result[Dict[str, Any], Exception]:
        """Test implementation - returns reset info"""
        info = {
            "available": self.reset_available,
            "recovery_mode": self.recovery_mode,
            "gpio_available": False,  # No GPIO in test environment
            "monitoring": False,
        }

        return Result.success(info)

    def set_recovery_mode(self, enabled: bool):
        """Test helper method to set recovery mode"""
        self.recovery_mode = enabled

    def set_reset_success(self, success: bool):
        """Test helper method to configure reset success/failure"""
        self.last_reset_successful = success


class TestDeviceInfoProvider(IDeviceInfoProvider):
    """Test implementation of device info provider with predictable behavior"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger

    def get_device_info(self) -> DeviceInfo:
        """Test implementation - returns test device info"""
        return DeviceInfo(
            device_id="TEST-DEVICE-001",
            mac_address="AA:BB:CC:DD:EE:FF",
            hardware_version="Test Hardware v1.0",
            firmware_version="Test Firmware v1.0",
            capabilities=["wifi", "bluetooth", "display", "test"],
        )

    def get_device_id(self) -> str:
        """Test implementation - returns test device ID"""
        return "TEST-DEVICE-001"

    def get_mac_address(self) -> str:
        """Test implementation - returns test MAC address"""
        return "AA:BB:CC:DD:EE:FF"

    def get_provisioning_code(self) -> str:
        """Test implementation - returns test provisioning code"""
        return "ROCKPI:TEST-DEVICE-001:AABBCCDDEEFF"
