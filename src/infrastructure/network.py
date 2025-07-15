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
    """Concrete implementation of network service with full async support"""

    def __init__(self, config: NetworkConfig, logger: Optional[ILogger] = None):
        self.config = config
        self.logger = logger
        self.current_connection: Optional[ConnectionInfo] = None
        self.cache = NetworkCache(config.network_scan_cache_ttl)
        self._scan_lock = asyncio.Lock()
        self._connection_lock = asyncio.Lock()
        self._active_operations: Dict[str, asyncio.Task] = {}

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
