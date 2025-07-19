"""
Infrastructure Layer - External dependencies and implementations
This layer contains concrete implementations of interfaces and handles external dependencies.
"""

from .bluetooth import BluetoothService
from .configuration_service import LocalConfigurationService as ConfigurationService
from .device import DeviceInfoProvider
try:
    from .display import DisplayService
except ImportError:
    # Fallback for refactored display service
    from .display.qr_generator import QRCodeGenerator
    DisplayService = None
from .factory_reset import FactoryResetService
from .health import HealthMonitorService
from .logging import LoggingService
from .network import NetworkService
from .ownership import OwnershipService
from .security import SecurityService

__all__ = [
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
]
