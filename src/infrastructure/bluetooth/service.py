"""
Main Bluetooth service implementation using refactored modules
"""

import asyncio
from typing import Any, Callable, Optional

from ...common.result_handling import Result
from ...domain.configuration import BLEConfig
from ...domain.errors import BLEError, ErrorCode, ErrorSeverity
from ...interfaces import DeviceInfo, IBluetoothService, ILogger
from .advertising import BluetoothAdvertisingManager
from .base import BluetoothServiceBase
from .recovery import BluetoothRecoveryManager


class BluetoothService(BluetoothServiceBase, IBluetoothService):
    """
    Concrete implementation of Bluetooth service with BLE 5.0 support for ROCK Pi 4B+
    Refactored into smaller, focused modules for better maintainability
    """

    def __init__(self, config: BLEConfig, logger: Optional[ILogger] = None):
        super().__init__(config, logger)
        
        # Initialize managers
        self.advertising_manager = BluetoothAdvertisingManager(self, logger)
        self.recovery_manager = BluetoothRecoveryManager(self, logger)
        
        self._log_info("Bluetooth service initialized with modular architecture")

    async def start_advertising(
        self, device_info: DeviceInfo, timeout: Optional[float] = None
    ) -> Result[bool, Exception]:
        """Start BLE advertising using advertising manager"""
        return await self.advertising_manager.start_advertising(device_info, timeout)

    async def stop_advertising(
        self, timeout: Optional[float] = None
    ) -> Result[bool, Exception]:
        """Stop BLE advertising using advertising manager"""
        return await self.advertising_manager.stop_advertising(timeout)

    async def monitor_connection_health(self, interval: float = 5.0) -> None:
        """Monitor BLE connection health"""
        await self.advertising_manager.monitor_connection_health(interval)

    async def cleanup_sessions(self) -> None:
        """Clean up BLE sessions and resources"""
        await self.advertising_manager.cleanup_sessions()

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup"""
        try:
            await self.stop_advertising()
        except Exception as e:
            self._log_error("Error during context manager cleanup", e)

    # Legacy sync methods for backwards compatibility
    def start_advertising_sync(self, device_info: DeviceInfo) -> Result[bool, Exception]:
        """Legacy sync version of start_advertising"""
        try:
            if not self.is_advertising_flag:
                self._log_info("Starting BLE advertising (sync wrapper)")
                # This is a simplified sync version
                self.is_advertising_flag = True
                return Result.success(True)
            else:
                return Result.success(True)
        except Exception as e:
            error_msg = f"BLE advertising failed: {str(e)}"
            self._log_error(error_msg, e)
            return Result.failure(
                self._create_ble_error(ErrorCode.BLE_ADVERTISING_FAILED, error_msg)
            )

    def stop_advertising_sync(self) -> Result[bool, Exception]:
        """Legacy sync version of stop_advertising"""
        try:
            if self.is_advertising_flag:
                self._log_info("Stopping BLE advertising (sync wrapper)")
                self.is_advertising_flag = False
                self._connection_state = "disconnected"
                return Result.success(True)
            else:
                return Result.success(True)
        except Exception as e:
            error_msg = f"BLE advertising stop failed: {str(e)}"
            self._log_error(error_msg, e)
            return Result.failure(
                self._create_ble_error(ErrorCode.BLE_ADVERTISING_FAILED, error_msg)
            )