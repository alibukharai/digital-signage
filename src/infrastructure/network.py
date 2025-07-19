"""
Network service implementation with consistent error handling using Result pattern
Enhanced with async support and performance monitoring
"""

import asyncio
import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..common.result_handling import Result
from ..domain.configuration import NetworkConfig
from ..domain.errors import ErrorCode, ErrorSeverity, NetworkError
from ..interfaces import (
    ConnectionInfo,
    ConnectionStatus,
    ILogger,
    INetworkService,
    NetworkInfo,
)


@dataclass
class PerformanceMetrics:
    """Performance metrics for network operations"""

    operation_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    success: bool = False
    error_message: Optional[str] = None

    def complete(self, success: bool = True, error_message: Optional[str] = None):
        """Mark operation as complete and calculate duration"""
        self.end_time = datetime.now()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.success = success
        self.error_message = error_message


class NetworkCache:
    """Simple caching mechanism for network scan results"""

    def __init__(self, cache_ttl_seconds: int = 30):
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cache: Dict[str, Any] = {}
        self._cache_timestamp: Optional[datetime] = None

    def get_cached_networks(self) -> Optional[List[NetworkInfo]]:
        """Get cached network scan results if still valid"""
        if (
            self._cache_timestamp
            and datetime.now() - self._cache_timestamp < self.cache_ttl
            and "networks" in self._cache
        ):
            return self._cache["networks"]
        return None

    def cache_networks(self, networks: List[NetworkInfo]) -> None:
        """Cache network scan results"""
        self._cache["networks"] = networks
        self._cache_timestamp = datetime.now()

    def invalidate(self) -> None:
        """Invalidate cache"""
        self._cache.clear()
        self._cache_timestamp = None


class NetworkService(INetworkService):
    """Enhanced network service with OP1 optimizations for ROCK Pi 4B+"""

    def __init__(self, config: NetworkConfig, logger: Optional[ILogger] = None):
        self.config = config
        self.logger = logger
        self.cache = NetworkCache(cache_ttl_seconds=30)
        self.performance_metrics: List[PerformanceMetrics] = []
        self._connection_status = ConnectionStatus.DISCONNECTED
        self._current_connection: Optional[ConnectionInfo] = None

        # Add async locks and resource management
        self._scan_lock = asyncio.Lock()
        self._connection_lock = asyncio.Lock()
        self._active_operations: Dict[str, asyncio.Task] = {}
        self._resource_cleanup_callbacks: List[callable] = []

        # ROCK Pi 4B+ specific network optimizations
        self.ethernet_interfaces = self._detect_ethernet_interfaces()
        self.wifi_interfaces = self._detect_wifi_interfaces()
        self.poe_capable = self._detect_poe_capability()
        self.hardware_platform = self._detect_hardware_platform()

        # Apply platform-specific optimizations on initialization
        if self.hardware_platform == "OP1":
            self._apply_op1_optimizations()

    def _detect_hardware_platform(self) -> str:
        """Detect hardware platform for optimization"""
        try:
            with open("/proc/device-tree/compatible", "r") as f:
                compatible = f.read().strip()
                if "rockchip,op1" in compatible or "rockchip,rk3399-op1" in compatible:
                    return "OP1"
                elif "rockchip,rk3399" in compatible:
                    return "RK3399"
        except Exception:
            pass
        return "UNKNOWN"

    def _detect_ethernet_interfaces(self) -> List[str]:
        """Detect available Ethernet interfaces"""
        try:
            result = subprocess.run(
                ["ip", "link", "show"], capture_output=True, text=True, timeout=5
            )
            interfaces = []
            for line in result.stdout.split("\n"):
                if "state UP" in line or "state DOWN" in line:
                    if any(prefix in line for prefix in ["eth", "enp", "eno"]):
                        interface = line.split(":")[1].strip()
                        interfaces.append(interface)
            return interfaces
        except subprocess.TimeoutExpired:
            if self.logger:
                self.logger.warning("Ethernet interface detection timed out")
            return []
        except subprocess.CalledProcessError as e:
            if self.logger:
                self.logger.warning(f"Command failed to detect Ethernet interfaces: {e}")
            return []
        except FileNotFoundError:
            if self.logger:
                self.logger.warning("Network tools not found for Ethernet detection")
            return []
        except OSError as e:
            if self.logger:
                self.logger.warning(f"System error detecting Ethernet interfaces: {e}")
            return []

    def _detect_wifi_interfaces(self) -> List[str]:
        """Detect available WiFi interfaces"""
        try:
            result = subprocess.run(
                ["iw", "dev"], capture_output=True, text=True, timeout=5
            )
            interfaces = []
            for line in result.stdout.split("\n"):
                if "Interface" in line:
                    interface = line.split("Interface")[1].strip()
                    interfaces.append(interface)
            return interfaces
        except subprocess.TimeoutExpired:
            if self.logger:
                self.logger.warning("WiFi interface detection timed out")
            return []
        except subprocess.CalledProcessError as e:
            if self.logger:
                self.logger.warning(f"Command failed to detect WiFi interfaces: {e}")
            return []
        except FileNotFoundError:
            if self.logger:
                self.logger.warning("Wireless tools not found for WiFi detection")
            return []
        except OSError as e:
            if self.logger:
                self.logger.warning(f"System error detecting WiFi interfaces: {e}")
            return []

    def _detect_poe_capability(self) -> bool:
        """Detect if PoE HAT is connected (ROCK Pi 4B+ feature)"""
        try:
            # Check for PoE HAT on I2C
            result = subprocess.run(
                ["i2cdetect", "-y", "1"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            # Common PoE HAT I2C addresses
            poe_addresses = ["51", "52", "53"]
            poe_detected = any(addr in result.stdout for addr in poe_addresses)

            if poe_detected and self.logger:
                self.logger.info("PoE HAT detected on ROCK Pi 4B+")

            return poe_detected

        except Exception:
            return False

    def _apply_op1_optimizations(self) -> bool:
        """Apply OP1-specific network optimizations"""
        try:
            optimizations_applied = 0

            # Optimize Ethernet interfaces
            for interface in self.ethernet_interfaces:
                try:
                    # Enable hardware offloading features available on OP1
                    optimizations = [
                        f"ethtool -K {interface} rx-checksumming on",
                        f"ethtool -K {interface} tx-checksumming on",
                        f"ethtool -K {interface} scatter-gather on",
                        f"ethtool -K {interface} tcp-segmentation-offload on",
                        f"ethtool -K {interface} generic-segmentation-offload on",
                        # Optimize ring buffers for OP1
                        f"ethtool -G {interface} rx 512 tx 512",
                    ]

                    for cmd in optimizations:
                        try:
                            subprocess.run(
                                cmd.split(), check=True, timeout=5, capture_output=True
                            )
                            optimizations_applied += 1
                            if self.logger:
                                self.logger.debug(f"Applied: {cmd}")
                        except subprocess.CalledProcessError:
                            # Some optimizations may not be supported, continue
                            pass

                except (subprocess.CalledProcessError, OSError, IOError) as e:
                    if self.logger:
                        self.logger.warning(
                            f"Ethernet optimization failed for {interface}: {e}"
                        )
                except Exception as e:
                    # Catch-all for unexpected errors, but log them as errors
                    if self.logger:
                        self.logger.error(
                            f"Unexpected error during ethernet optimization for {interface}: {e}"
                        )

            # Optimize WiFi power management for BT 5.0 coexistence
            for interface in self.wifi_interfaces:
                try:
                    # Disable aggressive power saving that might interfere with BLE
                    subprocess.run(
                        ["iwconfig", interface, "power", "off"],
                        check=True,
                        timeout=5,
                        capture_output=True,
                    )
                    optimizations_applied += 1
                    if self.logger:
                        self.logger.info(f"Disabled power management for {interface}")
                except subprocess.CalledProcessError:
                    # Power management may not be supported, continue
                    pass

            if self.logger:
                self.logger.info(
                    f"Applied {optimizations_applied} OP1 network optimizations"
                )

            return optimizations_applied > 0

        except (subprocess.CalledProcessError, OSError, IOError, FileNotFoundError) as e:
            if self.logger:
                self.logger.error(f"OP1 optimization failed: {e}")
            return False
        except Exception as e:
            # Unexpected error - log with more details for debugging
            if self.logger:
                self.logger.error(f"Unexpected OP1 optimization error: {type(e).__name__}: {e}")
            return False

    async def scan_networks(
        self, timeout: Optional[float] = None
    ) -> Result[List[NetworkInfo], Exception]:
        """Scan for available WiFi networks with async support and timeout"""
        operation_id = f"scan_{time.time()}"
        timeout = timeout or self.config.wifi_scan_timeout

        try:
            async with self._scan_lock:
                # Check cache first
                cached_networks = self.cache.get_cached_networks()
                if cached_networks is not None:
                    if self.logger:
                        self.logger.info("Using cached WiFi networks")
                    return Result.success(cached_networks)

                if self.logger:
                    self.logger.info(
                        f"Starting async WiFi network scan with timeout {timeout}s"
                    )

                # Create cancellable scan task
                scan_task = asyncio.create_task(self._perform_network_scan())
                self._active_operations[operation_id] = scan_task

                try:
                    networks = await asyncio.wait_for(scan_task, timeout=timeout)

                    if self.logger:
                        self.logger.info(f"Found {len(networks)} WiFi networks")

                    # Cache the results
                    self.cache.cache_networks(networks)
                    return Result.success(networks)

                except asyncio.TimeoutError:
                    scan_task.cancel()
                    error_msg = f"WiFi scan timed out after {timeout}s"
                    if self.logger:
                        self.logger.error(error_msg)
                    return Result.failure(
                        NetworkError(
                            ErrorCode.NETWORK_SCAN_FAILED,
                            error_msg,
                            ErrorSeverity.MEDIUM,
                        )
                    )
                finally:
                    self._active_operations.pop(operation_id, None)

        except Exception as e:
            error_msg = f"Failed to scan networks: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                NetworkError(
                    ErrorCode.NETWORK_SCAN_FAILED,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

    async def _perform_network_scan(self) -> List[NetworkInfo]:
        """Perform the actual network scan asynchronously"""
        networks = []

        # Run subprocess in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list"],
                capture_output=True,
                text=True,
                timeout=self.config.wifi_scan_timeout,
            ),
        )

        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split(":")
                    if len(parts) >= 3:
                        ssid = parts[0]
                        try:
                            signal = int(parts[1]) if parts[1] else 0
                        except ValueError:
                            signal = 0
                        security = parts[2] if len(parts) > 2 else "Open"

                        if ssid:  # Skip empty SSIDs
                            networks.append(
                                NetworkInfo(
                                    ssid=ssid,
                                    signal_strength=signal,
                                    security_type=security,
                                )
                            )
        return networks

    async def connect_to_network(
        self, ssid: str, password: str, timeout: Optional[float] = None
    ) -> Result[bool, Exception]:
        """Connect to a WiFi network with full async support and timeout"""
        operation_id = f"connect_{ssid}_{time.time()}"
        timeout = timeout or self.config.connection_timeout

        try:
            async with self._connection_lock:
                if self.logger:
                    self.logger.info(
                        f"Connecting to WiFi network: {ssid} with timeout {timeout}s"
                    )

                # Create cancellable connection task
                connect_task = asyncio.create_task(
                    self._perform_network_connection(ssid, password)
                )
                self._active_operations[operation_id] = connect_task

                try:
                    success = await asyncio.wait_for(connect_task, timeout=timeout)

                    if success:
                        # Verify connection with a brief delay
                        await asyncio.sleep(2)
                        if self.is_connected():
                            self.current_connection = ConnectionInfo(
                                status=ConnectionStatus.CONNECTED, ssid=ssid
                            )
                            if self.logger:
                                self.logger.info(f"Successfully connected to {ssid}")
                            return Result.success(True)
                        else:
                            error_msg = f"Connection to {ssid} failed verification"
                            if self.logger:
                                self.logger.error(error_msg)
                            return Result.failure(
                                NetworkError(
                                    ErrorCode.NETWORK_CONNECTION_FAILED,
                                    error_msg,
                                    ErrorSeverity.HIGH,
                                )
                            )
                    else:
                        error_msg = f"Failed to connect to {ssid}"
                        return Result.failure(
                            NetworkError(
                                ErrorCode.NETWORK_CONNECTION_FAILED,
                                error_msg,
                                ErrorSeverity.HIGH,
                            )
                        )

                except asyncio.TimeoutError:
                    connect_task.cancel()
                    error_msg = f"Connection to {ssid} timed out after {timeout}s"
                    if self.logger:
                        self.logger.error(error_msg)
                    return Result.failure(
                        NetworkError(
                            ErrorCode.NETWORK_TIMEOUT,
                            error_msg,
                            ErrorSeverity.MEDIUM,
                        )
                    )
                finally:
                    self._active_operations.pop(operation_id, None)

        except Exception as e:
            error_msg = f"Failed to connect to {ssid}: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                NetworkError(
                    ErrorCode.NETWORK_CONNECTION_FAILED,
                    error_msg,
                    ErrorSeverity.HIGH,
                )
            )

    async def _perform_network_connection(self, ssid: str, password: str) -> bool:
        """Perform the actual network connection asynchronously"""
        loop = asyncio.get_event_loop()

        # Run subprocess in thread pool to avoid blocking
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["nmcli", "device", "wifi", "connect", ssid, "password", password],
                capture_output=True,
                text=True,
                timeout=self.config.connection_timeout,
            ),
        )

        return result.returncode == 0

    async def disconnect(
        self, timeout: Optional[float] = None
    ) -> Result[bool, Exception]:
        """Disconnect from current network with async support and timeout"""
        timeout = timeout or 10.0  # Default 10 second timeout

        try:
            if self.logger:
                self.logger.info(f"Disconnecting from WiFi with timeout {timeout}s")

            # Create cancellable disconnection task
            disconnect_task = asyncio.create_task(self._perform_disconnect())

            try:
                success = await asyncio.wait_for(disconnect_task, timeout=timeout)

                if success:
                    self.current_connection = None
                    if self.logger:
                        self.logger.info("Disconnected from WiFi")
                    return Result.success(True)
                else:
                    error_msg = "Failed to disconnect from WiFi"
                    return Result.failure(
                        NetworkError(
                            ErrorCode.NETWORK_CONNECTION_FAILED,
                            error_msg,
                            ErrorSeverity.MEDIUM,
                        )
                    )

            except asyncio.TimeoutError:
                disconnect_task.cancel()
                error_msg = f"Disconnect operation timed out after {timeout}s"
                if self.logger:
                    self.logger.error(error_msg)
                return Result.failure(
                    NetworkError(
                        ErrorCode.NETWORK_TIMEOUT,
                        error_msg,
                        ErrorSeverity.MEDIUM,
                    )
                )

        except Exception as e:
            error_msg = f"Disconnect failed: {e}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                NetworkError(
                    ErrorCode.NETWORK_CONNECTION_FAILED,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

    async def _perform_disconnect(self) -> bool:
        """Perform the actual disconnection asynchronously"""
        loop = asyncio.get_event_loop()

        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["nmcli", "device", "disconnect", self.config.interface_name],
                capture_output=True,
                text=True,
            ),
        )

        return result.returncode == 0

    async def get_connection_info(self) -> Result[ConnectionInfo, Exception]:
        """Get current connection information with async support"""
        if not self.is_connected():
            return Result.success(ConnectionInfo(status=ConnectionStatus.DISCONNECTED))

        try:
            # Run connection info retrieval asynchronously
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    [
                        "nmcli",
                        "-t",
                        "-f",
                        "GENERAL.CONNECTION,IP4.ADDRESS",
                        "device",
                        "show",
                        self.config.interface_name,
                    ],
                    capture_output=True,
                    text=True,
                ),
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                ssid = None
                ip_address = None

                for line in lines:
                    if line.startswith("GENERAL.CONNECTION:"):
                        ssid = line.split(":", 1)[1]
                    elif line.startswith("IP4.ADDRESS[1]:"):
                        ip_part = line.split(":", 1)[1]
                        ip_address = (
                            ip_part.split("/")[0] if "/" in ip_part else ip_part
                        )

                return Result.success(
                    ConnectionInfo(
                        status=ConnectionStatus.CONNECTED,
                        ssid=ssid,
                        ip_address=ip_address,
                    )
                )

        except Exception as e:
            error_msg = f"Failed to get connection info: {e}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                NetworkError(
                    ErrorCode.NETWORK_CONNECTION_FAILED,
                    error_msg,
                    ErrorSeverity.LOW,
                )
            )

        return Result.success(ConnectionInfo(status=ConnectionStatus.CONNECTED))

    async def monitor_connection_quality(self, interval: float = 5.0) -> None:
        """Monitor connection quality continuously"""
        while True:
            try:
                if self.is_connected():
                    quality_info = await self._get_connection_quality()
                    if self.logger and quality_info:
                        signal_strength = quality_info.get("signal_strength", 0)
                        if signal_strength < 30:  # Weak signal threshold
                            self.logger.warning(
                                f"Weak WiFi signal detected: {signal_strength}%"
                            )
                await asyncio.sleep(interval)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Connection quality monitoring error: {e}")
                await asyncio.sleep(interval)

    async def _get_connection_quality(self) -> Optional[Dict[str, Any]]:
        """Get detailed connection quality information"""
        try:
            if not self.is_connected():
                return None

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["iwconfig", self.config.interface_name],
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                ),
            )

            if result.returncode == 0:
                output = result.stdout
                quality_info = {}

                # Parse signal strength
                import re

                signal_match = re.search(r"Signal level=(-?\d+)", output)
                if signal_match:
                    signal_dbm = int(signal_match.group(1))
                    # Convert dBm to percentage (rough approximation)
                    signal_percent = max(0, min(100, (signal_dbm + 100) * 2))
                    quality_info["signal_strength"] = signal_percent
                    quality_info["signal_dbm"] = signal_dbm

                # Parse link quality
                quality_match = re.search(r"Link Quality=(\d+)/(\d+)", output)
                if quality_match:
                    current = int(quality_match.group(1))
                    maximum = int(quality_match.group(2))
                    quality_info["link_quality"] = (current / maximum) * 100

                return quality_info

        except Exception as e:
            if self.logger:
                self.logger.debug(f"Could not get connection quality: {e}")

        return None

    async def get_connection_quality(self) -> Result[Dict[str, Any], Exception]:
        """Get current connection quality metrics"""
        try:
            quality_info = await self._get_connection_quality()
            if quality_info:
                return Result.success(quality_info)
            else:
                return Result.success({"signal_strength": 0, "link_quality": 0})
        except Exception as e:
            error_msg = f"Failed to get connection quality: {e}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                NetworkError(
                    ErrorCode.NETWORK_CONNECTION_FAILED,
                    error_msg,
                    ErrorSeverity.LOW,
                )
            )

    def cancel_all_operations(self) -> None:
        """Cancel all active network operations"""
        for operation_id, task in self._active_operations.items():
            if not task.done():
                task.cancel()
                if self.logger:
                    self.logger.info(f"Cancelled network operation: {operation_id}")
        self._active_operations.clear()

    def is_connected(self) -> bool:
        """Check if currently connected to WiFi"""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "DEVICE,STATE", "device", "status"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line.startswith(f"{self.config.interface_name}:"):
                        state = line.split(":")[1]
                        return state == "connected"

            return False

        except Exception as e:
            if self.logger:
                self.logger.error(f"Connection check failed: {e}")
            return False

    async def cleanup_resources(self) -> None:
        """Cleanup all network resources and active operations"""
        try:
            if self.logger:
                self.logger.info("Cleaning up network resources")

            # Cancel all active operations
            await self.cancel_all_operations()

            # Execute cleanup callbacks
            for callback in self._resource_cleanup_callbacks:
                try:
                    await callback()
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"Resource cleanup callback failed: {e}")

            # Clear caches
            self.cache.invalidate()
            self.performance_metrics.clear()

            # Reset connection state
            self._connection_status = ConnectionStatus.DISCONNECTED
            self._current_connection = None

            if self.logger:
                self.logger.info("Network resource cleanup completed")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error during network resource cleanup: {e}")

    def register_cleanup_callback(self, callback: callable) -> None:
        """Register a callback to be called during resource cleanup"""
        self._resource_cleanup_callbacks.append(callback)

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with proper cleanup"""
        await self.cleanup_resources()

    async def get_connection_health(self) -> Dict[str, Any]:
        """Get detailed connection health information"""
        try:
            health_info = {
                "connected": self.is_connected(),
                "connection_status": self._connection_status.value
                if hasattr(self._connection_status, "value")
                else str(self._connection_status),
                "current_connection": self._current_connection.__dict__
                if self._current_connection
                else None,
                "active_operations": len(self._active_operations),
                "ethernet_interfaces": self.ethernet_interfaces,
                "wifi_interfaces": self.wifi_interfaces,
                "poe_capable": self.poe_capable,
                "platform": self.hardware_platform,
                "cache_valid": self.cache.get_cached_networks() is not None,
            }

            # Add recent performance metrics
            recent_metrics = [
                m for m in self.performance_metrics[-5:]
            ]  # Last 5 operations
            health_info["recent_operations"] = [
                {
                    "operation": m.operation_name,
                    "duration_ms": m.duration_ms,
                    "success": m.success,
                    "error": m.error_message,
                }
                for m in recent_metrics
                if m.end_time is not None
            ]

            return health_info

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to get connection health: {e}")
            return {"error": str(e)}
