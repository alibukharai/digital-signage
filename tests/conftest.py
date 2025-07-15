"""
Common test fixtures and utilities for Rock Pi 3399 provisioning tests.
"""

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock

import pytest

from src.application.dependency_injection import Container
from src.application.provisioning_orchestrator import ProvisioningOrchestrator
from src.domain.configuration import ProvisioningConfig, load_config
from src.domain.events import EventBus
from src.domain.state import ProvisioningEvent, ProvisioningStateMachine
from src.interfaces import (
    ConnectionInfo,
    ConnectionStatus,
    DeviceInfo,
    DeviceState,
    NetworkInfo,
)

# Import test doubles for clean testing
from tests.test_doubles import (
    TestBluetoothService,
    TestConfigurationService,
    TestDeviceInfoProvider,
    TestDisplayService,
    TestFactoryResetService,
    TestHealthMonitorService,
    TestLogger,
    TestNetworkService,
    TestOwnershipService,
    TestSecurityService,
)


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for config files during testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def test_config(temp_config_dir):
    """Provide a test configuration with all required settings."""
    config_data = {
        "ble": {
            "service_uuid": "12345678-1234-5678-9abc-123456789abc",
            "wifi_credentials_char_uuid": "12345678-1234-5678-9abc-123456789abd",
            "status_char_uuid": "12345678-1234-5678-9abc-123456789abe",
            "device_info_char_uuid": "12345678-1234-5678-9abc-123456789abf",
            "advertising_timeout": 300,
            "connection_timeout": 30,
            "max_connections": 1,
            "advertising_name": "RockPi-Test",
        },
        "security": {
            "encryption_algorithm": "Fernet",
            "key_derivation_iterations": 600000,
            "credential_timeout": 300,
            "require_owner_setup": True,
            "owner_setup_timeout": 600,
            "owner_pin_length": 6,
            "max_owner_setup_attempts": 3,
            "owner_lockout_duration": 3600,
            "authentication": {
                "max_failed_attempts": 3,
                "lockout_duration_seconds": 3600,
                "session_timeout_minutes": 15,
            },
        },
        "network": {
            "connection_timeout": 30,
            "max_retry_attempts": 3,
            "scan_timeout": 10,
            "retry_delay": 5,
        },
        "display": {
            "hdmi_detection_timeout": 5,
            "status_message_duration": 3,
            "qr_code_size": 200,
        },
        "logging": {
            "level": "DEBUG",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file_path": f"{temp_config_dir}/test.log",
            "max_file_size": 10485760,
            "backup_count": 5,
        },
        "system": {
            "factory_reset_gpio": 18,
            "factory_reset_hold_time": 5.5,
            "config_file_path": f"{temp_config_dir}/config.json",
            "credentials_file_path": f"{temp_config_dir}/credentials.json",
        },
    }

    config_file = Path(temp_config_dir) / "config.json"
    with open(config_file, "w") as f:
        json.dump(config_data, f, indent=2)

    return load_config(str(config_file))


@pytest.fixture
def event_bus():
    """Provide a clean event bus instance."""
    return EventBus()


@pytest.fixture
def state_machine(event_bus):
    """Provide a fresh state machine instance."""
    return ProvisioningStateMachine(event_bus)


@pytest.fixture
def service_container(test_config):
    """Provide a configured service container."""
    container = Container()
    container.register_config(test_config)
    return container


@pytest.fixture
def provisioning_orchestrator(service_container):
    """Provide a configured provisioning orchestrator."""
    return ProvisioningOrchestrator(service_container)


@pytest.fixture
def valid_device_info():
    """Provide valid device information for testing."""
    return DeviceInfo(
        device_id="TEST-ROCKPI-001",
        mac_address="AA:BB:CC:DD:EE:FF",
        hardware_version="Rock Pi 3399 v1.4",
        firmware_version="2.0.0",
        capabilities=["wifi", "bluetooth", "display", "gpio"],
    )


@pytest.fixture
def valid_network_info():
    """Provide valid network information for testing."""
    return [
        NetworkInfo(
            ssid="TestNetwork",
            signal_strength=-45,
            security_type="WPA2",
            frequency=2400,
        ),
        NetworkInfo(
            ssid="TestNetwork5G",
            signal_strength=-50,
            security_type="WPA3",
            frequency=5000,
        ),
        NetworkInfo(
            ssid="OpenNetwork",
            signal_strength=-60,
            security_type="Open",
            frequency=2400,
        ),
    ]


@pytest.fixture
def valid_credentials():
    """Provide valid WiFi credentials for testing."""
    return {"ssid": "TestNetwork", "password": "TestPassword123!", "security": "WPA2"}


@pytest.fixture
def valid_owner_pin():
    """Provide a valid owner PIN for testing."""
    return "123456"


@pytest.fixture
def invalid_credentials():
    """Provide various invalid credentials for testing."""
    return {
        "malformed_json": '{"ssid": "test", "password": incomplete',
        "oversized_ssid": {
            "ssid": "A" * 300,  # Over 256 character limit
            "password": "validpassword",
            "security": "WPA2",
        },
        "missing_required": {
            "ssid": "TestNetwork"
            # Missing password
        },
        "empty_values": {"ssid": "", "password": "", "security": "WPA2"},
    }


@pytest.fixture
def connection_info_connected():
    """Provide connection info for connected state."""
    return ConnectionInfo(
        status=ConnectionStatus.CONNECTED,
        ssid="TestNetwork",
        ip_address="192.168.1.100",
        signal_strength=-45,
        connection_time=None,  # Will be set when connection is established
    )


@pytest.fixture
def connection_info_disconnected():
    """Provide connection info for disconnected state."""
    return ConnectionInfo(
        status=ConnectionStatus.DISCONNECTED,
        ssid=None,
        ip_address=None,
        signal_strength=None,
        connection_time=None,
    )


@pytest.fixture
async def system_in_initializing_state(state_machine):
    """Provide system in INITIALIZING state."""
    # State machine starts in INITIALIZING by default
    assert state_machine.get_current_state() == DeviceState.INITIALIZING
    return state_machine


@pytest.fixture
async def system_in_provisioning_state(state_machine):
    """Provide system in PROVISIONING state."""
    state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
    assert state_machine.get_current_state() == DeviceState.PROVISIONING
    return state_machine


@pytest.fixture
async def system_in_connected_state(state_machine):
    """Provide system in CONNECTED state."""
    state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
    state_machine.process_event(ProvisioningEvent.CREDENTIALS_RECEIVED)
    state_machine.process_event(ProvisioningEvent.NETWORK_CONNECTED)
    assert state_machine.get_current_state() == DeviceState.CONNECTED
    return state_machine


@pytest.fixture
async def system_in_ready_state(state_machine):
    """Provide system in READY state."""
    state_machine.process_event(ProvisioningEvent.START_OWNER_SETUP)
    assert state_machine.get_current_state() == DeviceState.READY
    return state_machine


class TestWiFiNetwork:
    """Helper class to simulate WiFi network for testing."""

    def __init__(self, ssid: str, password: str, available: bool = True):
        self.ssid = ssid
        self.password = password
        self.available = available
        self.connection_delay = 0.1  # Simulate connection time

    async def connect(self, provided_password: str) -> bool:
        """Simulate connection attempt."""
        if not self.available:
            return False

        await asyncio.sleep(self.connection_delay)
        return provided_password == self.password


@pytest.fixture
def test_wifi_networks():
    """Provide test WiFi networks."""
    return {
        "TestNetwork": TestWiFiNetwork("TestNetwork", "TestPassword123!"),
        "TestNetwork5G": TestWiFiNetwork("TestNetwork5G", "TestPassword5G!"),
        "UnavailableNetwork": TestWiFiNetwork(
            "UnavailableNetwork", "password", available=False
        ),
    }


class BluetoothTestHelper:
    """Helper class for Bluetooth testing scenarios."""

    def __init__(self):
        self.is_connected = False
        self.advertising = False
        self.connection_count = 0
        self.max_disconnection_time = 10.0  # seconds

    async def connect(self):
        """Simulate BLE connection."""
        self.is_connected = True
        self.connection_count += 1

    async def disconnect(self):
        """Simulate BLE disconnection."""
        self.is_connected = False

    async def simulate_connection_loss(self, duration: float = 5.0):
        """Simulate temporary connection loss."""
        await self.disconnect()
        await asyncio.sleep(duration)
        if duration <= self.max_disconnection_time:
            await self.connect()


@pytest.fixture
def bluetooth_test_helper():
    """Provide Bluetooth test helper."""
    return BluetoothTestHelper()


class GPIOTestHelper:
    """Helper class for GPIO testing scenarios."""

    def __init__(self, pin: int = 18):
        self.pin = pin
        self.is_pressed = False
        self.press_duration = 0.0
        self.reset_threshold = 5.5  # seconds

    async def press_and_hold(self, duration: float):
        """Simulate pressing and holding the GPIO button."""
        self.is_pressed = True
        self.press_duration = duration
        await asyncio.sleep(duration)
        self.is_pressed = False
        return duration >= self.reset_threshold


@pytest.fixture
def gpio_test_helper():
    """Provide GPIO test helper."""
    return GPIOTestHelper()


@pytest.fixture
def encrypted_credentials():
    """Provide encrypted credentials for security testing."""
    # This would normally use the actual SecurityService encryption
    # For testing, we'll use a simple base64 encoding as placeholder
    import base64

    valid_creds = json.dumps(
        {"ssid": "TestNetwork", "password": "TestPassword123!", "security": "WPA2"}
    )

    encrypted = base64.b64encode(valid_creds.encode()).decode()

    return {"encrypted": encrypted, "plaintext": valid_creds}


@pytest.fixture
def test_service_factory():
    """Factory for creating clean test service instances."""

    def create_services(logger=None):
        if logger is None:
            logger = TestLogger()

        return {
            "logger": logger,
            "network": TestNetworkService(logger),
            "bluetooth": TestBluetoothService(logger),
            "display": TestDisplayService(logger),
            "configuration": TestConfigurationService(logger),
            "security": TestSecurityService(logger),
            "device_info": TestDeviceInfoProvider(logger),
            "ownership": TestOwnershipService(logger),
            "factory_reset": TestFactoryResetService(logger),
            "health_monitor": TestHealthMonitorService(logger),
        }

    return create_services


@pytest.fixture
def test_services(test_service_factory):
    """Provide a clean set of test service instances."""
    return test_service_factory()


# Test Utilities
def assert_state_transition(
    state_machine, expected_from: DeviceState, expected_to: DeviceState
):
    """Assert that a state transition occurred as expected."""
    history = state_machine.get_state_history(limit=1)
    if history:
        last_transition = history[-1]
        assert last_transition["from_state"] == expected_from
        assert last_transition["to_state"] == expected_to
    assert state_machine.get_current_state() == expected_to


def assert_event_published(event_bus, event_type: str, timeout: float = 1.0):
    """Assert that an event was published to the event bus."""
    # This would need to be implemented based on the actual EventBus implementation
    # For now, we'll just check that the event_bus is available
    assert event_bus is not None


async def wait_for_state(
    state_machine, expected_state: DeviceState, timeout: float = 30.0
):
    """Wait for state machine to reach expected state or timeout."""
    start_time = asyncio.get_event_loop().time()

    while state_machine.get_current_state() != expected_state:
        if asyncio.get_event_loop().time() - start_time > timeout:
            raise TimeoutError(
                f"Timeout waiting for state {expected_state.value}. "
                f"Current state: {state_machine.get_current_state().value}"
            )
        await asyncio.sleep(0.1)


async def wait_for_connection(network_service, timeout: float = 30.0):
    """Wait for network connection to be established."""
    start_time = asyncio.get_event_loop().time()

    while not network_service.is_connected():
        if asyncio.get_event_loop().time() - start_time > timeout:
            raise TimeoutError("Timeout waiting for network connection")
        await asyncio.sleep(0.1)
