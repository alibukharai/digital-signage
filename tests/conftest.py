"""
Integration test fixtures and utilities for Rock Pi 4B+ provisioning tests.
Uses real service implementations with test configurations instead of mocks.
"""

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional
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

# Import integration test adapters instead of mocks
from tests.integration.test_adapters import (
    TestEnvironmentConfig,
    IntegrationTestLogger,
    IntegrationNetworkService,
    IntegrationBluetoothService,
    IntegrationDisplayService,
    IntegrationConfigurationService,
    create_integration_test_environment,
    IntegrationTestAssertions,
)


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for config files during testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def test_environment_config(temp_config_dir):
    """Create test environment configuration with isolated temp directory."""
    config = TestEnvironmentConfig(
        temp_dir=Path(temp_config_dir),
        simulated_networks=[
            NetworkInfo(ssid="TestNetwork_WPA2", signal_strength=-45, security_type="WPA2"),
            NetworkInfo(ssid="TestNetwork_WPA3", signal_strength=-50, security_type="WPA3"),
            NetworkInfo(ssid="TestNetwork_Open", signal_strength=-60, security_type="Open"),
            NetworkInfo(ssid="Enterprise_Network", signal_strength=-55, security_type="WPA2-Enterprise"),
        ],
        device_info=DeviceInfo(
            device_id="TEST-ROCKPI4B-001",
            mac_address="AA:BB:CC:DD:EE:FF",
            hardware_version="ROCK Pi 4B+ Test",
            firmware_version="Test Firmware v1.0.0",
            capabilities=["wifi", "bluetooth", "display", "gpio", "test_mode"],
        ),
        enable_real_bluetooth=False,  # Use simulated BLE for safety
        enable_real_network=False,    # Use simulated network for safety
        health_check_interval=0.1     # Fast health checks for testing
    )
    return config


@pytest.fixture
def integration_services(test_environment_config):
    """Create real service instances with test configurations."""
    config, services = create_integration_test_environment(test_environment_config)
    yield services
    
    # Cleanup after test
    if hasattr(config, 'temp_dir') and config.temp_dir.exists():
        shutil.rmtree(config.temp_dir, ignore_errors=True)


@pytest.fixture
def logger(integration_services):
    """Get the integration test logger."""
    return integration_services["logger"]


@pytest.fixture
def network_service(integration_services):
    """Get the integration network service."""
    return integration_services["network"]


@pytest.fixture  
def bluetooth_service(integration_services):
    """Get the integration bluetooth service."""
    return integration_services["bluetooth"]


@pytest.fixture
def display_service(integration_services):
    """Get the integration display service."""
    return integration_services["display"]


@pytest.fixture
def configuration_service(integration_services):
    """Get the integration configuration service."""
    return integration_services["configuration"]


@pytest.fixture
def device_info_service(test_environment_config):
    """Create a real device info service with test data."""
    from src.infrastructure.device import DeviceInfoProvider
    
    class TestDeviceInfoProvider(DeviceInfoProvider):
        def __init__(self, test_config: TestEnvironmentConfig):
            super().__init__()
            self._test_device_info = test_config.device_info
        
        def get_device_info(self) -> DeviceInfo:
            return self._test_device_info
        
        def get_device_id(self) -> str:
            return self._test_device_info.device_id
        
        def get_mac_address(self) -> str:
            return self._test_device_info.mac_address
        
        def get_provisioning_code(self) -> str:
            return f"ROCKPI:{self._test_device_info.device_id}:{self._test_device_info.mac_address.replace(':', '')}"
    
    return TestDeviceInfoProvider(test_environment_config)


@pytest.fixture
def event_bus():
    """Create a real event bus for testing."""
    return EventBus()


@pytest.fixture
def state_machine(event_bus):
    """Create a real state machine with event bus."""
    return ProvisioningStateMachine(event_bus)


@pytest.fixture
def provisioning_config(temp_config_dir):
    """Create test provisioning configuration."""
    config_data = {
        "bluetooth": {
            "advertising_timeout": 300,
            "connection_timeout": 30,
            "service_uuid": "12345678-1234-5678-9abc-123456789abc",
            "advertising_name": "RockPi-Test"
        },
        "network": {
            "connection_timeout": 30,
            "scan_timeout": 10,
            "max_retry_attempts": 3,
            "interface_name": "test-wlan0"
        },
        "display": {
            "resolution_width": 1920,
            "resolution_height": 1080,
            "qr_size_ratio": 0.3,
            "fullscreen": True
        },
        "security": {
            "encryption_algorithm": "Fernet",
            "key_derivation_iterations": 100000,  # Reduced for testing
            "require_owner_setup": False,  # Simplified for testing
            "enhanced_security": True
        },
        "logging": {
            "level": "DEBUG",
            "detailed_logs": True,
            "log_file": f"{temp_config_dir}/test.log"
        }
    }
    
    config_file = Path(temp_config_dir) / "test_config.json"
    with open(config_file, 'w') as f:
        json.dump(config_data, f, indent=2)
    
    return ProvisioningConfig.from_file(config_file)


@pytest.fixture
def container(
    integration_services,
    device_info_service,
    event_bus,
    state_machine,
    provisioning_config
):
    """Create a real dependency injection container with test services."""
    container = Container()
    
    # Register real services with test configurations
    container.register_singleton("logger", lambda: integration_services["logger"])
    container.register_singleton("network_service", lambda: integration_services["network"])
    container.register_singleton("bluetooth_service", lambda: integration_services["bluetooth"])
    container.register_singleton("display_service", lambda: integration_services["display"])
    container.register_singleton("configuration_service", lambda: integration_services["configuration"])
    container.register_singleton("device_info_service", lambda: device_info_service)
    container.register_singleton("event_bus", lambda: event_bus)
    container.register_singleton("state_machine", lambda: state_machine)
    container.register_singleton("config", lambda: provisioning_config)
    
    return container


@pytest.fixture
async def provisioning_orchestrator(container):
    """Create a real provisioning orchestrator with integrated services."""
    orchestrator = ProvisioningOrchestrator(container)
    
    # Initialize the orchestrator
    await orchestrator.initialize()
    
    yield orchestrator
    
    # Cleanup
    try:
        await orchestrator.shutdown()
    except Exception:
        pass  # Ignore cleanup errors in tests


@pytest.fixture
def valid_credentials():
    """Valid network credentials for testing."""
    return {
        "ssid": "TestNetwork_WPA2",
        "password": "TestPassword123",
        "security_type": "WPA2"
    }


@pytest.fixture
def invalid_credentials():
    """Invalid network credentials for testing."""
    return {
        "ssid": "",
        "password": "short",
        "security_type": "WPA2"
    }


@pytest.fixture
def enterprise_credentials():
    """Enterprise network credentials for testing."""
    return {
        "ssid": "Enterprise_Network", 
        "username": "test.user@company.com",
        "password": "EnterprisePassword123",
        "security_type": "WPA2-Enterprise",
        "certificate": "test_cert_data"
    }


# Integration test assertion helpers
@pytest.fixture
def assert_helper():
    """Get integration test assertion helpers."""
    return IntegrationTestAssertions


# Async test utilities
@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Helper functions for common test operations
async def wait_for_state(state_machine: ProvisioningStateMachine, target_state: DeviceState, timeout: float = 5.0):
    """Wait for state machine to reach target state within timeout."""
    start_time = asyncio.get_event_loop().time()
    
    while state_machine.current_state != target_state:
        if asyncio.get_event_loop().time() - start_time > timeout:
            raise TimeoutError(f"State machine did not reach {target_state} within {timeout}s")
        await asyncio.sleep(0.01)


async def wait_for_connection(network_service: IntegrationNetworkService, timeout: float = 5.0):
    """Wait for network service to establish connection within timeout."""
    start_time = asyncio.get_event_loop().time()
    
    while not network_service.is_connected():
        if asyncio.get_event_loop().time() - start_time > timeout:
            raise TimeoutError(f"Network did not connect within {timeout}s")
        await asyncio.sleep(0.01)


async def assert_state_transition(
    state_machine: ProvisioningStateMachine,
    event: ProvisioningEvent,
    expected_state: DeviceState,
    timeout: float = 2.0
):
    """Assert that processing an event leads to expected state transition."""
    initial_state = state_machine.current_state
    
    # Process the event
    state_machine.process_event(event)
    
    # Wait for state transition
    await wait_for_state(state_machine, expected_state, timeout)
    
    assert state_machine.current_state == expected_state, (
        f"Expected state {expected_state}, but got {state_machine.current_state} "
        f"after processing {event} from {initial_state}"
    )


def create_test_network_info(ssid: str, security_type: str = "WPA2", signal_strength: int = -50) -> NetworkInfo:
    """Create a NetworkInfo object for testing."""
    return NetworkInfo(
        ssid=ssid,
        signal_strength=signal_strength,
        security_type=security_type
    )


def create_test_device_info(device_id: str = "TEST-DEVICE") -> DeviceInfo:
    """Create a DeviceInfo object for testing."""
    return DeviceInfo(
        device_id=device_id,
        mac_address="AA:BB:CC:DD:EE:FF",
        hardware_version="Test Hardware v1.0",
        firmware_version="Test Firmware v1.0",
        capabilities=["wifi", "bluetooth", "display", "test"]
    )


# Test configuration validation
def validate_test_environment():
    """Validate that test environment is properly configured."""
    try:
        # Check that integration test adapters can be imported
        from tests.integration.test_adapters import create_integration_test_environment
        
        # Create a test environment to verify it works
        config, services = create_integration_test_environment()
        
        # Verify all required services are present
        required_services = ["logger", "network", "bluetooth", "display", "configuration"]
        for service_name in required_services:
            assert service_name in services, f"Missing required service: {service_name}"
        
        return True
        
    except Exception as e:
        pytest.fail(f"Test environment validation failed: {str(e)}")


# Run validation when conftest is loaded
validate_test_environment()
