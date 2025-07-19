"""
Base classes and common functionality for Bluetooth services
"""

import asyncio
import threading
import time
from typing import Any, Callable, Dict, Optional

from ...common.result_handling import Result
from ...domain.configuration import BLEConfig
from ...domain.errors import BLEError, ErrorCode, ErrorSeverity
from ...interfaces import DeviceInfo, ILogger

# Try to import BLE libraries
try:
    from bleak import BleakAdapter, BleakPeripheral
    from bleak.backends.characteristic import BleakGATTCharacteristic
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False


class BluetoothServiceBase:
    """Base class for Bluetooth service with common functionality"""
    
    def __init__(self, config: BLEConfig, logger: Optional[ILogger] = None):
        self.config = config
        self.logger = logger
        self.is_advertising_flag = False
        self.credentials_callback: Optional[Callable[[str, str], None]] = None
        self.peripheral: Optional[Any] = None
        self.adapter: Optional[Any] = None

        # Recovery and session management with synchronization
        self._connection_attempts = 0
        self._max_reconnection_attempts = 5
        self._reconnection_delay = 10.0  # 10 seconds as per test requirements
        self._session_data = {}
        self._last_heartbeat = 0
        self._recovery_thread = None
        self._should_recover = False

        # Add synchronization primitives for BLE recovery
        self._recovery_lock = asyncio.Lock()
        self._recovery_in_progress = False
        self._session_lock = asyncio.Lock()
        self._cleanup_task = None

        # Enhanced connection state tracking for BLE 5.0
        self._connection_state = "disconnected"  # disconnected, connecting, connected, recovering
        self._last_disconnection_time = 0
        self._session_backup = {}  # Backup of session data for recovery
        self._pending_credentials = None  # Store incomplete credentials during transfer

        # BLE 5.0 specific features
        self._multiple_connections = {}  # Track multiple concurrent connections
        self._extended_advertising_data = {}
        self._phy_mode = "2M"  # Start with 2M PHY for better performance
        self._max_concurrent_connections = getattr(config, "max_connections", 3)

        if not BLEAK_AVAILABLE:
            if self.logger:
                self.logger.warning(
                    "Bleak library not available, BLE functionality will be simulated"
                )

    def _log_error(self, message: str, exception: Optional[Exception] = None) -> None:
        """Log error with consistent formatting"""
        if self.logger:
            if exception:
                self.logger.error(f"{message}: {str(exception)}")
            else:
                self.logger.error(message)

    def _log_info(self, message: str) -> None:
        """Log info with consistent formatting"""
        if self.logger:
            self.logger.info(message)

    def _log_debug(self, message: str) -> None:
        """Log debug with consistent formatting"""
        if self.logger:
            self.logger.debug(message)

    def _create_ble_error(self, code: ErrorCode, message: str, 
                         severity: ErrorSeverity = ErrorSeverity.MEDIUM) -> BLEError:
        """Create standardized BLE error"""
        return BLEError(code, message, severity)

    def is_advertising(self) -> bool:
        """Check if currently advertising"""
        return self.is_advertising_flag

    def set_credentials_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set callback for credential reception"""
        self.credentials_callback = callback
        self._log_debug("Credentials callback set")