"""
Domain Interfaces - Pure abstractions for the provisioning system
This layer contains only interfaces and has no dependencies on other layers.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


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
    """Network connectivity service"""
    
    @abstractmethod
    def scan_networks(self) -> List[NetworkInfo]:
        """Scan for available networks"""
        pass
    
    @abstractmethod
    def connect_to_network(self, ssid: str, password: str) -> bool:
        """Connect to a network"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from current network"""
        pass
    
    @abstractmethod
    def get_connection_info(self) -> ConnectionInfo:
        """Get current connection information"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if currently connected"""
        pass


class IBluetoothService(ABC):
    """Bluetooth communication service"""
    
    @abstractmethod
    def start_advertising(self, device_info: DeviceInfo) -> bool:
        """Start BLE advertising"""
        pass
    
    @abstractmethod
    def stop_advertising(self) -> bool:
        """Stop BLE advertising"""
        pass
    
    @abstractmethod
    def is_advertising(self) -> bool:
        """Check if currently advertising"""
        pass
    
    @abstractmethod
    def set_credentials_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set callback for received credentials"""
        pass


class IDisplayService(ABC):
    """Display management service"""
    
    @abstractmethod
    def show_qr_code(self, data: str) -> bool:
        """Display QR code"""
        pass
    
    @abstractmethod
    def show_status(self, message: str) -> bool:
        """Display status message"""
        pass
    
    @abstractmethod
    def clear_display(self) -> bool:
        """Clear the display"""
        pass
    
    @abstractmethod
    def is_display_active(self) -> bool:
        """Check if display is active"""
        pass


class ISecurityService(ABC):
    """Security and encryption service"""
    
    @abstractmethod
    def encrypt_data(self, data: str, key_id: Optional[str] = None) -> bytes:
        """Encrypt data"""
        pass
    
    @abstractmethod
    def decrypt_data(self, encrypted_data: bytes, key_id: Optional[str] = None) -> str:
        """Decrypt data"""
        pass
    
    @abstractmethod
    def validate_credentials(self, ssid: str, password: str) -> bool:
        """Validate network credentials"""
        pass
    
    @abstractmethod
    def create_session(self, client_id: str) -> str:
        """Create secure session"""
        pass


class IConfigurationService(ABC):
    """Configuration management service"""
    
    @abstractmethod
    def save_network_config(self, ssid: str, password: str) -> bool:
        """Save network configuration"""
        pass
    
    @abstractmethod
    def load_network_config(self) -> Optional[Tuple[str, str]]:
        """Load saved network configuration"""
        pass
    
    @abstractmethod
    def clear_network_config(self) -> bool:
        """Clear saved network configuration"""
        pass
    
    @abstractmethod
    def has_network_config(self) -> bool:
        """Check if network config exists"""
        pass


class IHealthMonitor(ABC):
    """System health monitoring"""
    
    @abstractmethod
    def check_system_health(self) -> Dict[str, Any]:
        """Perform system health check"""
        pass
    
    @abstractmethod
    def start_monitoring(self) -> bool:
        """Start continuous monitoring"""
        pass
    
    @abstractmethod
    def stop_monitoring(self) -> bool:
        """Stop monitoring"""
        pass
    
    @abstractmethod
    def get_health_status(self) -> str:
        """Get current health status"""
        pass


class IOwnershipService(ABC):
    """Device ownership management"""
    
    @abstractmethod
    def is_owner_registered(self) -> bool:
        """Check if owner is registered"""
        pass
    
    @abstractmethod
    def register_owner(self, pin: str, name: str) -> Tuple[bool, str]:
        """Register device owner"""
        pass
    
    @abstractmethod
    def authenticate_owner(self, pin: str) -> Tuple[bool, str]:
        """Authenticate owner"""
        pass
    
    @abstractmethod
    def start_setup_mode(self) -> bool:
        """Start owner setup mode"""
        pass


class IFactoryResetService(ABC):
    """Factory reset functionality"""
    
    @abstractmethod
    def is_reset_available(self) -> bool:
        """Check if reset is available"""
        pass
    
    @abstractmethod
    def perform_reset(self, confirmation_code: str) -> Tuple[bool, str]:
        """Perform factory reset"""
        pass
    
    @abstractmethod
    def get_reset_info(self) -> Dict[str, Any]:
        """Get reset information"""
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
