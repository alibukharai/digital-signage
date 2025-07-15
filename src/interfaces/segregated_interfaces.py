"""
Segregated interfaces following ISP
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class HealthMetric:
    """Represents a health metric"""

    name: str
    value: Any
    status: str  # "healthy", "warning", "critical"
    timestamp: float


@dataclass
class SystemStatus:
    """Overall system status"""

    overall_health: str
    metrics: List[HealthMetric]
    last_check: float


# Segregated interfaces instead of one large IHealthMonitor
class IHealthChecker(ABC):
    """Interface for checking system health"""

    @abstractmethod
    def check_health(self) -> SystemStatus:
        """Perform health check"""
        pass


class IHealthReporter(ABC):
    """Interface for reporting health status"""

    @abstractmethod
    def report_status(self, status: SystemStatus) -> None:
        """Report health status"""
        pass


class IHealthMonitoring(ABC):
    """Interface for health monitoring lifecycle"""

    @abstractmethod
    def start_monitoring(self) -> bool:
        """Start monitoring"""
        pass

    @abstractmethod
    def stop_monitoring(self) -> bool:
        """Stop monitoring"""
        pass

    @abstractmethod
    def is_monitoring(self) -> bool:
        """Check if monitoring is active"""
        pass


class INetworkConnectivity(ABC):
    """Interface specifically for network connectivity"""

    @abstractmethod
    def connect_to_network(self, ssid: str, password: str) -> bool:
        """Connect to network"""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from network"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check connection status"""
        pass


class INetworkScanning(ABC):
    """Interface specifically for network scanning"""

    @abstractmethod
    def scan_networks(self) -> List[Any]:  # NetworkInfo
        """Scan for available networks"""
        pass


class INetworkInformation(ABC):
    """Interface for network information"""

    @abstractmethod
    def get_connection_info(self) -> Any:  # ConnectionInfo
        """Get current connection information"""
        pass


# Original interfaces can compose these smaller ones
class INetworkService(INetworkConnectivity, INetworkScanning, INetworkInformation):
    """Complete network service interface"""

    pass


class IFullHealthMonitor(IHealthChecker, IHealthReporter, IHealthMonitoring):
    """Complete health monitoring interface"""

    pass


# Clients can depend on only what they need
class NetworkConnector:
    """Example class that only needs connectivity"""

    def __init__(self, connectivity: INetworkConnectivity):
        self.connectivity = connectivity

    def connect(self, ssid: str, password: str) -> bool:
        return self.connectivity.connect_to_network(ssid, password)


class NetworkScanner:
    """Example class that only needs scanning"""

    def __init__(self, scanner: INetworkScanning):
        self.scanner = scanner

    def find_networks(self):
        return self.scanner.scan_networks()


class HealthReporter:
    """Example class that only needs to check health"""

    def __init__(self, checker: IHealthChecker):
        self.checker = checker

    def get_status(self):
        return self.checker.check_health()
