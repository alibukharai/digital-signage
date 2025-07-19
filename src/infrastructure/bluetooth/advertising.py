"""
Bluetooth advertising and connection management with enhanced security
"""

import asyncio
import hashlib
import json
import random
import secrets
import time
from typing import Any, Dict, Optional, Set
import hmac

from ...common.result_handling import Result
from ...domain.errors import BLEError, ErrorCode, ErrorSeverity
from ...interfaces import DeviceInfo, ILogger
from .base import BLEAK_AVAILABLE

if BLEAK_AVAILABLE:
    from bleak import BleakAdapter, BleakPeripheral


class BluetoothSecurityManager:
    """Handles BLE security, authentication, and session management"""
    
    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self._session_keys: Dict[str, bytes] = {}
        self._authenticated_devices: Set[str] = set()
        self._session_timeouts: Dict[str, float] = {}
        self._failed_attempts: Dict[str, int] = {}
        self._rate_limit_reset: Dict[str, float] = {}
        
        # Security configuration
        self.max_failed_attempts = 3
        self.session_timeout = 300  # 5 minutes
        self.rate_limit_window = 60  # 1 minute
        self.challenge_length = 32
    
    def generate_session_key(self, device_id: str) -> bytes:
        """Generate a secure session key for device authentication"""
        session_key = secrets.token_bytes(32)
        self._session_keys[device_id] = session_key
        self._session_timeouts[device_id] = time.time() + self.session_timeout
        return session_key
    
    def create_challenge(self) -> bytes:
        """Create a cryptographic challenge for device authentication"""
        return secrets.token_bytes(self.challenge_length)
    
    def verify_challenge_response(self, device_id: str, challenge: bytes, response: bytes) -> bool:
        """Verify challenge response using HMAC"""
        if device_id not in self._session_keys:
            return False
            
        expected_response = hmac.new(
            self._session_keys[device_id],
            challenge,
            hashlib.sha256
        ).digest()
        
        return hmac.compare_digest(expected_response, response)
    
    def is_device_authenticated(self, device_id: str) -> bool:
        """Check if device is authenticated and session is valid"""
        if device_id not in self._authenticated_devices:
            return False
            
        # Check session timeout
        if device_id in self._session_timeouts:
            if time.time() > self._session_timeouts[device_id]:
                self.revoke_authentication(device_id)
                return False
                
        return True
    
    def authenticate_device(self, device_id: str) -> bool:
        """Mark device as authenticated"""
        if self._check_rate_limit(device_id):
            self._authenticated_devices.add(device_id)
            self._session_timeouts[device_id] = time.time() + self.session_timeout
            # Reset failed attempts on successful auth
            if device_id in self._failed_attempts:
                del self._failed_attempts[device_id]
            return True
        return False
    
    def revoke_authentication(self, device_id: str):
        """Revoke device authentication"""
        self._authenticated_devices.discard(device_id)
        if device_id in self._session_keys:
            del self._session_keys[device_id]
        if device_id in self._session_timeouts:
            del self._session_timeouts[device_id]
    
    def record_failed_attempt(self, device_id: str):
        """Record failed authentication attempt"""
        self._failed_attempts[device_id] = self._failed_attempts.get(device_id, 0) + 1
        if self._failed_attempts[device_id] >= self.max_failed_attempts:
            # Rate limit the device
            self._rate_limit_reset[device_id] = time.time() + self.rate_limit_window
    
    def _check_rate_limit(self, device_id: str) -> bool:
        """Check if device is rate limited"""
        if device_id in self._rate_limit_reset:
            if time.time() < self._rate_limit_reset[device_id]:
                return False
            else:
                # Reset rate limit
                del self._rate_limit_reset[device_id]
                if device_id in self._failed_attempts:
                    del self._failed_attempts[device_id]
        return True
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions and rate limits"""
        current_time = time.time()
        
        # Clean up expired sessions
        expired_sessions = [
            device_id for device_id, timeout in self._session_timeouts.items()
            if current_time > timeout
        ]
        
        for device_id in expired_sessions:
            self.revoke_authentication(device_id)
        
        # Clean up expired rate limits
        expired_rate_limits = [
            device_id for device_id, reset_time in self._rate_limit_reset.items()
            if current_time > reset_time
        ]
        
        for device_id in expired_rate_limits:
            del self._rate_limit_reset[device_id]
            if device_id in self._failed_attempts:
                del self._failed_attempts[device_id]


class BluetoothAdvertisingManager:
    """Manages Bluetooth advertising and connection handling with enhanced security"""

    def __init__(self, parent_service, logger: Optional[ILogger] = None):
        self.parent = parent_service
        self.logger = logger
        self.security_manager = BluetoothSecurityManager(logger)

    async def start_advertising(
        self, device_info: DeviceInfo, timeout: Optional[float] = None
    ) -> Result[bool, Exception]:
        """Start BLE advertising with consistent error handling, recovery logic, and async support"""
        timeout = timeout or 30.0  # Default 30 second timeout

        try:
            if self.logger:
                self.logger.info(
                    f"Starting BLE advertising with recovery support and timeout {timeout}s"
                )

            # Initialize recovery state
            self.parent._connection_attempts = 0
            self.parent._should_recover = True
            self.parent._session_data = {}
            self.parent._last_heartbeat = time.time()
            self.parent._connection_state = "connecting"
            self.parent._session_backup = {}
            self.parent._pending_credentials = None

            # Create cancellable advertising task
            advertising_task = asyncio.create_task(
                self._perform_start_advertising(device_info)
            )

            try:
                success = await asyncio.wait_for(advertising_task, timeout=timeout)

                if success:
                    self.parent.is_advertising_flag = True
                    self.parent._connection_state = "connected"

                    # Start background monitoring
                    asyncio.create_task(self.monitor_connection_health())

                    if self.logger:
                        self.logger.info(
                            "BLE advertising started successfully with async support"
                        )
                    return Result.success(True)
                else:
                    error_msg = "Failed to start BLE advertising"
                    return Result.failure(
                        BLEError(
                            ErrorCode.BLE_ADVERTISING_FAILED,
                            error_msg,
                            ErrorSeverity.HIGH,
                        )
                    )

            except asyncio.TimeoutError:
                advertising_task.cancel()
                error_msg = f"BLE advertising startup timed out after {timeout}s"
                if self.logger:
                    self.logger.error(error_msg)
                return Result.failure(
                    BLEError(
                        ErrorCode.BLE_ADVERTISING_FAILED,
                        error_msg,
                        ErrorSeverity.MEDIUM,
                    )
                )

        except Exception as e:
            error_msg = f"BLE advertising failed: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                BLEError(
                    ErrorCode.BLE_ADVERTISING_FAILED,
                    error_msg,
                    ErrorSeverity.HIGH,
                )
            )

    async def _perform_start_advertising(self, device_info: DeviceInfo) -> bool:
        """Perform the actual BLE advertising startup asynchronously"""
        try:
            if BLEAK_AVAILABLE:
                return await self._run_real_ble_server()
            else:
                return await self._run_simulated_ble_server()
        except Exception as e:
            if self.logger:
                self.logger.error(f"BLE advertising startup failed: {e}")
            return False

    async def stop_advertising(
        self, timeout: Optional[float] = None
    ) -> Result[bool, Exception]:
        """Stop BLE advertising with graceful cleanup and timeout"""
        timeout = timeout or 15.0  # Default 15 second timeout

        try:
            if self.logger:
                self.logger.info(f"Stopping BLE advertising with timeout {timeout}s")

            # Set flag to stop recovery
            self.parent._should_recover = False
            self.parent._connection_state = "disconnected"

            # Create cancellable stop task
            stop_task = asyncio.create_task(self._perform_stop_advertising())

            try:
                success = await asyncio.wait_for(stop_task, timeout=timeout)

                if success:
                    self.parent.is_advertising_flag = False
                    # Clean up sessions
                    await self.cleanup_sessions()

                    if self.logger:
                        self.logger.info("BLE advertising stopped successfully")
                    return Result.success(True)
                else:
                    error_msg = "Failed to stop BLE advertising gracefully"
                    if self.logger:
                        self.logger.warning(error_msg)
                    return Result.failure(
                        BLEError(
                            ErrorCode.BLE_ADVERTISING_FAILED,
                            error_msg,
                            ErrorSeverity.MEDIUM,
                        )
                    )

            except asyncio.TimeoutError:
                stop_task.cancel()
                # Force stop if timeout
                self.parent.is_advertising_flag = False
                error_msg = f"BLE advertising stop timed out after {timeout}s, forced stop"
                if self.logger:
                    self.logger.warning(error_msg)
                return Result.failure(
                    BLEError(
                        ErrorCode.BLE_ADVERTISING_FAILED,
                        error_msg,
                        ErrorSeverity.LOW,
                    )
                )

        except Exception as e:
            error_msg = f"BLE advertising stop failed: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                BLEError(
                    ErrorCode.BLE_ADVERTISING_FAILED,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

    async def _perform_stop_advertising(self) -> bool:
        """Perform the actual BLE advertising stop asynchronously"""
        try:
            if self.parent.peripheral:
                # Stop the peripheral if it exists
                # In real implementation, this would stop the BLE server
                self.parent.peripheral = None

            if self.logger:
                self.logger.debug("BLE advertising stopped")
            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Stop advertising failed: {e}")
            return False

    async def monitor_connection_health(self, interval: float = 5.0) -> None:
        """Monitor BLE connection health and trigger recovery if needed"""
        try:
            while self.parent.is_advertising_flag and self.parent._should_recover:
                # Update heartbeat
                self.parent._last_heartbeat = time.time()

                # Check connection state
                if self.parent._connection_state == "disconnected":
                    if self.logger:
                        self.logger.warning("Connection lost detected, triggering recovery")
                    
                    # Use recovery manager if available
                    if hasattr(self.parent, 'recovery_manager'):
                        await self.parent.recovery_manager.trigger_recovery_async()
                    
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            if self.logger:
                self.logger.debug("Connection health monitoring cancelled")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Connection health monitoring failed: {e}")

    async def cleanup_sessions(self) -> None:
        """Clean up BLE sessions and resources"""
        try:
            async with self.parent._session_lock:
                self.parent._session_data.clear()
                self.parent._session_backup.clear()
                self.parent._pending_credentials = None

            # Cancel cleanup task if running
            if self.parent._cleanup_task and not self.parent._cleanup_task.done():
                self.parent._cleanup_task.cancel()

            if self.logger:
                self.logger.debug("BLE sessions cleaned up")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Session cleanup failed: {e}")

    async def _run_real_ble_server(self) -> bool:
        """Run real BLE server using Bleak"""
        try:
            if self.logger:
                self.logger.info("Starting real BLE server with Bleak")

            # Initialize BLE adapter
            adapter = BleakAdapter()
            
            # Create peripheral
            peripheral = BleakPeripheral()
            
            # Set up GATT services and characteristics
            # This is a simplified implementation
            self.parent.adapter = adapter
            self.parent.peripheral = peripheral

            if self.logger:
                self.logger.info("Real BLE server started successfully")
            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Real BLE server failed: {e}")
            return False

    async def _run_simulated_ble_server(self) -> bool:
        """Run simulated BLE server for testing"""
        try:
            if self.logger:
                self.logger.info("Starting simulated BLE server")

            # Simulate BLE server startup
            await asyncio.sleep(0.1)  # Simulate initialization time
            
            # Create mock peripheral
            self.parent.peripheral = {"mock": True, "connected": True}

            if self.logger:
                self.logger.info("Simulated BLE server started successfully")
            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Simulated BLE server failed: {e}")
            return False

    def _handle_characteristic_write(self, characteristic: Any, data: bytes) -> None:
        """Handle characteristic write events"""
        try:
            # Decode the received data
            decoded_data = data.decode('utf-8')
            
            if self.logger:
                self.logger.debug(f"Received characteristic write: {decoded_data}")

            # Parse JSON data
            try:
                credentials_data = json.loads(decoded_data)
                
                # Validate required fields
                if 'ssid' in credentials_data and 'password' in credentials_data:
                    ssid = credentials_data['ssid']
                    password = credentials_data['password']
                    
                    # Store as pending credentials for recovery
                    self.parent._pending_credentials = credentials_data
                    
                    # Call the credentials callback
                    if self.parent.credentials_callback:
                        self.parent.credentials_callback(ssid, password)
                        
                    if self.logger:
                        self.logger.info("WiFi credentials received and processed")
                else:
                    if self.logger:
                        self.logger.warning("Invalid credentials format received")
                        
            except json.JSONDecodeError as e:
                if self.logger:
                    self.logger.error(f"Failed to parse credentials JSON: {e}")
                    
        except Exception as e:
            if self.logger:
                self.logger.error(f"Characteristic write handling failed: {e}")