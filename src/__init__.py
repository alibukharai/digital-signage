"""
Rock Pi 3399 Provisioning System
A layered architecture implementation for WiFi/BLE network provisioning
"""

# Application layer imports
from .application.dependency_injection import Container, ServiceLifetime
from .application.provisioning_orchestrator import ProvisioningOrchestrator
from .application.use_cases import (
    FactoryResetUseCase,
    NetworkProvisioningUseCase,
    OwnerSetupUseCase,
    SystemHealthUseCase,
)

# Explicit imports to prevent namespace pollution and circular import issues
# Domain layer imports
from .domain.configuration import ProvisioningConfig, load_config
from .domain.errors import ErrorCode, ErrorSeverity, ProvisioningError
from .domain.events import EventBus
from .domain.state import ProvisioningStateMachine
from .domain.validation import ValidationService
from .infrastructure.bluetooth import BluetoothService
from .infrastructure.configuration_service import (
    LocalConfigurationService as ConfigurationService,
)
from .infrastructure.device import DeviceInfoProvider
from .infrastructure.display import DisplayService
from .infrastructure.factory_reset import FactoryResetService
from .infrastructure.health import HealthMonitorService

# Infrastructure layer imports
from .infrastructure.logging import LoggingService
from .infrastructure.network import NetworkService
from .infrastructure.ownership import OwnershipService
from .infrastructure.security import SecurityService

__version__ = "2.0.0"
__author__ = "Rock Pi Provisioning Team"

# Main entry point
from .application.provisioning_orchestrator import main

__all__ = [
    "main",
    # Domain exports
    "ProvisioningConfig",
    "load_config",
    "ProvisioningError",
    "ErrorCode",
    "ErrorSeverity",
    "EventBus",
    "ValidationService",
    "ProvisioningStateMachine",
    # Infrastructure exports
    "LoggingService",
    "NetworkService",
    "BluetoothService",
    "DisplayService",
    "SecurityService",
    "ConfigurationService",
    "DeviceInfoProvider",
    "HealthMonitorService",
    "OwnershipService",
    "FactoryResetService",
    # Application exports
    "Container",
    "ServiceLifetime",
    "ProvisioningOrchestrator",
    "NetworkProvisioningUseCase",
    "OwnerSetupUseCase",
    "FactoryResetUseCase",
    "SystemHealthUseCase",
]
