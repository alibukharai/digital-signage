"""
Domain Interfaces - Pure abstractions for the provisioning system
This layer contains only interfaces and has no dependencies on other layers.
Following SOLID principles and using Result pattern for consistent error handling
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Union

if TYPE_CHECKING:
    from ..common.result_handling import Result
else:
    # Import Result for runtime use
    try:
        from ..common.result_handling import Result
    except ImportError:
        # Fallback for cases where circular imports might occur
        Result = Any


# Core value objects and enums
class ConnectionStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    FAILED = "failed"


class DeviceState(Enum):
    INITIALIZING = "initializing"
    READY = "ready"
    PROVISIONING = "provisioning"
    CONNECTED = "connected"
    ERROR = "error"
    FACTORY_RESET = "factory_reset"


class ProvisioningEvent(Enum):
    """Events that occur during provisioning process"""

    STARTED = "started"
    NETWORK_SCAN_REQUESTED = "network_scan_requested"
    NETWORK_SCAN_COMPLETED = "network_scan_completed"
    CREDENTIALS_RECEIVED = "credentials_received"
    NETWORK_CONNECTION_STARTED = "network_connection_started"
    NETWORK_CONNECTION_SUCCESS = "network_connection_success"
    NETWORK_CONNECTION_FAILED = "network_connection_failed"
    PROVISIONING_COMPLETED = "provisioning_completed"
    PROVISIONING_FAILED = "provisioning_failed"
    FACTORY_RESET_REQUESTED = "factory_reset_requested"


class SecurityLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class NetworkInfo:
    ssid: str
    signal_strength: int
    security_type: str
    frequency: Optional[int] = None


@dataclass
class DeviceInfo:
    device_id: str
    mac_address: str
    hardware_version: str
    firmware_version: str
    capabilities: List[str]


@dataclass
class ConnectionInfo:
    status: ConnectionStatus
    ssid: Optional[str] = None
    ip_address: Optional[str] = None
    signal_strength: Optional[int] = None
    connection_time: Optional[datetime] = None


# Core domain interfaces
class IDeviceInfoProvider(ABC):
    """Provides device information"""

    @abstractmethod
    def get_device_info(self) -> DeviceInfo:
        """Get comprehensive device information"""
        pass

    @abstractmethod
    def get_device_id(self) -> str:
        """Get unique device identifier"""
        pass

    @abstractmethod
    def get_mac_address(self) -> str:
        """Get device MAC address"""
        pass

    @abstractmethod
    def get_provisioning_code(self) -> str:
        """Get provisioning code for QR"""
        pass


class INetworkService(ABC):
    """Network connectivity service with consistent error handling and async support"""

    @abstractmethod
    async def scan_networks(
        self, timeout: Optional[float] = None
    ) -> "Result[List[NetworkInfo], Exception]":
        """Scan for available networks with async support and timeout - returns Result pattern"""
        pass

    @abstractmethod
    async def connect_to_network(
        self, ssid: str, password: str, timeout: Optional[float] = None
    ) -> "Result[bool, Exception]":
        """Connect to a network with async support and timeout - returns Result pattern"""
        pass

    @abstractmethod
    async def disconnect(
        self, timeout: Optional[float] = None
    ) -> "Result[bool, Exception]":
        """Disconnect from current network with async support and timeout - returns Result pattern"""
        pass

    @abstractmethod
    async def get_connection_info(self) -> "Result[ConnectionInfo, Exception]":
        """Get current connection information with async support - returns Result pattern"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if currently connected to WiFi - synchronous for quick status checks"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if currently connected - simple boolean check"""
        pass


class IBluetoothService(ABC):
    """Bluetooth communication service with consistent error handling and async support"""

    @abstractmethod
    async def start_advertising(
        self, device_info: DeviceInfo, timeout: Optional[float] = None
    ) -> "Result[bool, Exception]":
        """Start BLE advertising with async support and timeout - returns Result pattern"""
        pass

    @abstractmethod
    async def stop_advertising(
        self, timeout: Optional[float] = None
    ) -> "Result[bool, Exception]":
        """Stop BLE advertising with async support and timeout - returns Result pattern"""
        pass

    @abstractmethod
    def is_advertising(self) -> bool:
        """Check if currently advertising - simple boolean check"""
        pass

    @abstractmethod
    def set_credentials_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set callback for received credentials"""
        pass

    @abstractmethod
    async def monitor_connection_health(self, interval: float = 5.0) -> None:
        """Monitor BLE connection health continuously"""
        pass


class IDisplayService(ABC):
    """Display management service with consistent error handling"""

    @abstractmethod
    def show_qr_code(self, data: str) -> "Result[bool, Exception]":
        """Display QR code - returns Result pattern"""
        pass

    @abstractmethod
    def show_status(self, message: str) -> "Result[bool, Exception]":
        """Display status message - returns Result pattern"""
        pass

    @abstractmethod
    def clear_display(self) -> "Result[bool, Exception]":
        """Clear the display - returns Result pattern"""
        pass

    @abstractmethod
    def is_display_active(self) -> bool:
        """Check if display is active - simple boolean check"""
        pass


class ISecurityService(ABC):
    """Security and encryption service"""

    @abstractmethod
    def encrypt_data(
        self, data: str, key_id: Optional[str] = None
    ) -> Result[bytes, Exception]:
        """Encrypt data using Result pattern for consistent error handling"""
        pass

    @abstractmethod
    def decrypt_data(
        self, encrypted_data: bytes, key_id: Optional[str] = None
    ) -> Result[str, Exception]:
        """Decrypt data using Result pattern for consistent error handling"""
        pass

    @abstractmethod
    def validate_credentials(self, ssid: str, password: str) -> Result[bool, Exception]:
        """Validate network credentials using Result pattern for consistent error handling"""
        pass

    @abstractmethod
    def create_session(self, client_id: str) -> Result[str, Exception]:
        """Create secure session using Result pattern for consistent error handling"""
        pass


class IConfigurationService(ABC):
    """Configuration management service with consistent error handling"""

    @abstractmethod
    def save_network_config(
        self, ssid: str, password: str
    ) -> "Result[bool, Exception]":
        """Save network configuration - returns Result pattern"""
        pass

    @abstractmethod
    def load_network_config(self) -> "Result[Optional[Tuple[str, str]], Exception]":
        """Load saved network configuration - returns Result pattern"""
        pass

    @abstractmethod
    def clear_network_config(self) -> "Result[bool, Exception]":
        """Clear saved network configuration - returns Result pattern"""
        pass

    @abstractmethod
    def has_network_config(self) -> bool:
        """Check if network config exists - simple boolean check"""
        pass


class IHealthMonitor(ABC):
    """System health monitoring"""

    @abstractmethod
    def check_system_health(self) -> Result[Dict[str, Any], Exception]:
        """Perform system health check using Result pattern for consistent error handling"""
        pass

    @abstractmethod
    def start_monitoring(self) -> Result[bool, Exception]:
        """Start continuous monitoring using Result pattern for consistent error handling"""
        pass

    @abstractmethod
    def stop_monitoring(self) -> Result[bool, Exception]:
        """Stop monitoring using Result pattern for consistent error handling"""
        pass

    @abstractmethod
    def get_health_status(self) -> Result[str, Exception]:
        """Get current health status using Result pattern for consistent error handling"""
        pass


class IOwnershipService(ABC):
    """Device ownership management"""

    @abstractmethod
    def is_owner_registered(self) -> bool:
        """Check if owner is registered"""
        pass

    @abstractmethod
    def register_owner(self, pin: str, name: str) -> Result[bool, Exception]:
        """Register device owner using Result pattern for consistent error handling"""
        pass

    @abstractmethod
    def authenticate_owner(self, pin: str) -> Result[bool, Exception]:
        """Authenticate owner using Result pattern for consistent error handling"""
        pass

    @abstractmethod
    def start_setup_mode(self) -> Result[bool, Exception]:
        """Start owner setup mode using Result pattern for consistent error handling"""
        pass


class IFactoryResetService(ABC):
    """Factory reset functionality"""

    @abstractmethod
    def is_reset_available(self) -> bool:
        """Check if reset is available"""
        pass

    @abstractmethod
    def perform_reset(self, confirmation_code: str) -> Result[bool, Exception]:
        """Perform factory reset using Result pattern for consistent error handling"""
        pass

    @abstractmethod
    def get_reset_info(self) -> Result[Dict[str, Any], Exception]:
        """Get reset information using Result pattern for consistent error handling"""
        pass


class ILogger(ABC):
    """Logging interface"""

    @abstractmethod
    def debug(self, message: str, **kwargs) -> None:
        pass

    @abstractmethod
    def info(self, message: str, **kwargs) -> None:
        pass

    @abstractmethod
    def warning(self, message: str, **kwargs) -> None:
        pass

    @abstractmethod
    def error(self, message: str, **kwargs) -> None:
        pass

    @abstractmethod
    def critical(self, message: str, **kwargs) -> None:
        pass


class IEventBus(ABC):
    """Event bus for decoupled communication"""

    @abstractmethod
    def publish(self, event_type: str, data: Any) -> None:
        """Publish an event"""
        pass

    @abstractmethod
    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> str:
        """Subscribe to events"""
        pass

    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events"""
        pass


# Missing domain interfaces for better testability
class IValidationService(ABC):
    """Interface for validation operations"""

    @abstractmethod
    def validate_ssid(self, ssid: str) -> bool:
        """Validate network SSID"""
        pass

    @abstractmethod
    def validate_password(self, password: str) -> bool:
        """Validate network password"""
        pass

    @abstractmethod
    def validate_credentials(self, ssid: str, password: str) -> bool:
        """Validate complete network credentials"""
        pass


class IStateMachine(ABC):
    """Interface for state machine operations"""

    @abstractmethod
    def get_current_state(self) -> DeviceState:
        """Get current state"""
        pass

    @abstractmethod
    def process_event(self, event: Any, data: Any = None) -> bool:
        """Process state machine event"""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset state machine to initial state"""
        pass

    @abstractmethod
    def get_context(self, key: str) -> Any:
        """Get context value"""
        pass

    @abstractmethod
    def set_context(self, key: str, value: Any) -> None:
        """Set context value"""
        pass


# Segregated health monitoring interfaces (ISP compliant)
class IHealthChecker(ABC):
    """Interface for performing health checks"""

    @abstractmethod
    def check_system_health(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        pass


class IHealthMonitoring(ABC):
    """Interface for health monitoring lifecycle"""

    @abstractmethod
    def start_monitoring(self) -> bool:
        """Start continuous health monitoring"""
        pass

    @abstractmethod
    def stop_monitoring(self) -> bool:
        """Stop health monitoring"""
        pass

    @abstractmethod
    def is_monitoring(self) -> bool:
        """Check if monitoring is active"""
        pass


class IHealthReporter(ABC):
    """Interface for health status reporting"""

    @abstractmethod
    def get_health_status(self) -> str:
        """Get current health status"""
        pass

    @abstractmethod
    def get_health_metrics(self) -> Dict[str, Any]:
        """Get detailed health metrics"""
        pass


# Segregated network interfaces (ISP compliant)
class INetworkConnectivity(ABC):
    """Interface for network connectivity operations"""

    @abstractmethod
    def connect_to_network(self, ssid: str, password: str) -> bool:
        """Connect to a network"""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from current network"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to network"""
        pass


class INetworkScanning(ABC):
    """Interface for network scanning operations"""

    @abstractmethod
    def scan_networks(self) -> List[NetworkInfo]:
        """Scan for available networks"""
        pass

    @abstractmethod
    def refresh_scan(self) -> bool:
        """Refresh network scan"""
        pass


class INetworkInformation(ABC):
    """Interface for network information access"""

    @abstractmethod
    def get_connection_info(self) -> Optional[ConnectionInfo]:
        """Get current connection information"""
        pass

    @abstractmethod
    def get_signal_strength(self) -> int:
        """Get current signal strength"""
        pass


# Configuration interfaces (segregated)
class IConfigurationReader(ABC):
    """Interface for reading configuration"""

    @abstractmethod
    def load_network_config(self) -> Optional[Tuple[str, str]]:
        """Load network configuration"""
        pass


class IConfigurationWriter(ABC):
    """Interface for writing configuration"""

    @abstractmethod
    def save_network_config(self, ssid: str, password: str) -> bool:
        """Save network configuration"""
        pass

    @abstractmethod
    def clear_network_config(self) -> bool:
        """Clear network configuration"""
        pass


__all__ = [
    "ConnectionStatus",
    "DeviceState",
    "ProvisioningEvent",
    "SecurityLevel",
    "NetworkInfo",
    "DeviceInfo",
    "ConnectionInfo",
    "IDeviceInfoProvider",
    "INetworkService",
    "IBluetoothService",
    "IDisplayService",
    "ISecurityService",
    "IConfigurationService",
    "IHealthMonitor",
    "IOwnershipService",
    "IFactoryResetService",
    "ILogger",
    "IEventBus",
    "IHealthChecker",
    "IHealthReporter",
    "IHealthMonitoring",
    "INetworkConnectivity",
    "INetworkScanning",
    "INetworkInformation",
    "IConfigurationReader",
    "IConfigurationWriter",
    "IValidationService",
    "IStateMachine",
    "ProvisioningEvent",
]
