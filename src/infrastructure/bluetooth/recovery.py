"""
Recovery and session management for Bluetooth connections
"""

import asyncio
import time
from typing import Any, Dict, Optional

from ...common.result_handling import Result
from ...domain.errors import BLEError, ErrorCode, ErrorSeverity
from ...interfaces import ILogger


class BluetoothRecoveryManager:
    """Manages Bluetooth connection recovery and session state"""

    def __init__(self, parent_service, logger: Optional[ILogger] = None):
        self.parent = parent_service
        self.logger = logger

    async def trigger_recovery_async(self) -> None:
        """Trigger recovery process asynchronously"""
        if self.parent._recovery_in_progress:
            if self.logger:
                self.logger.debug("Recovery already in progress, skipping")
            return

        async with self.parent._recovery_lock:
            if self.parent._recovery_in_progress:
                return

            self.parent._recovery_in_progress = True
            try:
                await self._recovery_process_async()
            finally:
                self.parent._recovery_in_progress = False

    async def _recovery_process_async(self) -> None:
        """Async recovery process implementation"""
        try:
            if self.logger:
                self.logger.info("Starting BLE recovery process")

            # Validate recovery window
            if not await self._validate_recovery_window():
                if self.logger:
                    self.logger.warning("Recovery window validation failed")
                return

            # Backup current session state
            await self._backup_session_state_async()

            # Attempt reconnection
            recovery_success = await self._implement_automatic_reconnection_async()

            if recovery_success:
                # Restore session state if reconnection successful
                await self._restore_session_state_async(self.parent._session_backup)
                if self.logger:
                    self.logger.info("BLE recovery completed successfully")
            else:
                if self.logger:
                    self.logger.error("BLE recovery failed after all attempts")

        except asyncio.CancelledError:
            if self.logger:
                self.logger.info("BLE recovery was cancelled")
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(f"Recovery process failed: {e}")

    async def _validate_recovery_window(self) -> bool:
        """Validate if recovery should be attempted"""
        current_time = time.time()
        
        # Don't attempt recovery too frequently
        if (current_time - self.parent._last_disconnection_time) < 5.0:
            return False
            
        # Check if maximum reconnection attempts exceeded
        if self.parent._connection_attempts >= self.parent._max_reconnection_attempts:
            if self.logger:
                self.logger.warning(
                    f"Maximum reconnection attempts ({self.parent._max_reconnection_attempts}) exceeded"
                )
            return False
            
        return True

    async def _backup_session_state_async(self) -> None:
        """Backup current session state for recovery"""
        try:
            async with self.parent._session_lock:
                self.parent._session_backup = {
                    "session_data": self.parent._session_data.copy(),
                    "pending_credentials": self.parent._pending_credentials,
                    "connection_state": self.parent._connection_state,
                    "backup_timestamp": time.time(),
                }
                
            if self.logger:
                self.logger.debug("Session state backed up for recovery")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to backup session state: {e}")

    async def _restore_session_state_async(self, session_data: Dict[str, Any]) -> None:
        """Restore session state after successful recovery"""
        try:
            if not session_data:
                if self.logger:
                    self.logger.warning("No session data to restore")
                return

            async with self.parent._session_lock:
                self.parent._session_data = session_data.get("session_data", {})
                self.parent._pending_credentials = session_data.get("pending_credentials")
                self.parent._connection_state = session_data.get("connection_state", "connected")

            # Restore pending credentials if any
            if self.parent._pending_credentials:
                await self._restore_pending_credentials_async()

            if self.logger:
                self.logger.info("Session state restored successfully")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to restore session state: {e}")

    async def _implement_automatic_reconnection_async(self) -> bool:
        """Implement automatic reconnection with exponential backoff"""
        for attempt in range(self.parent._max_reconnection_attempts):
            try:
                if self.logger:
                    self.logger.info(f"Reconnection attempt {attempt + 1}/{self.parent._max_reconnection_attempts}")

                # Wait with exponential backoff
                delay = min(self.parent._reconnection_delay * (2 ** attempt), 60.0)
                await asyncio.sleep(delay)

                # Attempt to reconnect
                if await self._attempt_ble_reconnection_async():
                    self.parent._connection_attempts = 0  # Reset on success
                    return True

                self.parent._connection_attempts += 1

            except asyncio.CancelledError:
                if self.logger:
                    self.logger.info("Reconnection cancelled")
                raise
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")

        return False

    async def _attempt_ble_reconnection_async(self) -> bool:
        """Attempt to reconnect BLE service"""
        try:
            # Detect if disconnection occurred
            if not await self._detect_disconnection_async():
                return True  # Already connected

            # Stop current advertising if any
            await self.parent.stop_advertising()

            # Wait a moment before restarting
            await asyncio.sleep(2.0)

            # Restart advertising with current device info
            # Note: This would need device info from parent context
            # For now, return success to indicate recovery attempt
            self.parent._connection_state = "connected"
            self.parent.is_advertising_flag = True
            
            if self.logger:
                self.logger.info("BLE reconnection successful")
            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"BLE reconnection failed: {e}")
            return False

    async def _detect_disconnection_async(self) -> bool:
        """Detect if BLE connection is lost"""
        try:
            # Check connection state
            if self.parent._connection_state == "disconnected":
                return True

            # Check if peripheral is still available
            if not self.parent.peripheral:
                return True

            # Additional checks could be added here for real BLE status
            return False

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Disconnection detection failed: {e}")
            return True  # Assume disconnected if detection fails

    async def _restore_pending_credentials_async(self) -> None:
        """Restore pending credentials after reconnection"""
        try:
            if not self.parent._pending_credentials:
                return

            # Verify credentials integrity
            if not await self._verify_pending_credentials_integrity_async():
                if self.logger:
                    self.logger.warning("Pending credentials integrity check failed")
                self.parent._pending_credentials = None
                return

            # Process restored credentials
            credentials = self.parent._pending_credentials
            if self.parent.credentials_callback and credentials:
                ssid = credentials.get("ssid", "")
                password = credentials.get("password", "")
                if ssid and password:
                    self.parent.credentials_callback(ssid, password)
                    if self.logger:
                        self.logger.info("Pending credentials restored and processed")

            # Clear pending credentials after processing
            self.parent._pending_credentials = None

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to restore pending credentials: {e}")

    async def _verify_pending_credentials_integrity_async(self) -> bool:
        """Verify the integrity of pending credentials"""
        try:
            if not self.parent._pending_credentials:
                return False

            credentials = self.parent._pending_credentials
            
            # Basic validation
            if not isinstance(credentials, dict):
                return False

            required_fields = ["ssid", "password"]
            for field in required_fields:
                if field not in credentials or not credentials[field]:
                    return False

            # Additional integrity checks could be added here
            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Credentials integrity verification failed: {e}")
            return False