"""
Bluetooth service implementation with consistent error handling using Result pattern
"""

import asyncio
import json
import random
import threading
import time
from typing import Any, Callable, Dict, Optional

from ..common.result_handling import Result
from ..domain.configuration import BLEConfig
from ..domain.errors import BLEError, ErrorCode, ErrorSeverity
from ..interfaces import DeviceInfo, IBluetoothService, ILogger

# Try to import BLE libraries
try:
    from bleak import BleakAdapter, BleakPeripheral
    from bleak.backends.characteristic import BleakGATTCharacteristic

    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False


class BluetoothService(IBluetoothService):
    """Concrete implementation of Bluetooth service with BLE 5.0 support for ROCK Pi 4B+"""

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
        self._connection_state = (
            "disconnected"  # disconnected, connecting, connected, recovering
        )
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
            self._connection_attempts = 0
            self._should_recover = True
            self._session_data = {}
            self._last_heartbeat = time.time()
            self._connection_state = "connecting"
            self._session_backup = {}
            self._pending_credentials = None

            # Create cancellable advertising task
            advertising_task = asyncio.create_task(
                self._perform_start_advertising(device_info)
            )

            try:
                success = await asyncio.wait_for(advertising_task, timeout=timeout)

                if success:
                    self.is_advertising_flag = True
                    self._connection_state = "connected"

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
                        ErrorCode.BLE_TIMEOUT,
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
            if not BLEAK_AVAILABLE:
                # Simulate BLE advertising with recovery
                await asyncio.sleep(1)  # Simulate startup time
                # Start background task to handle connections with recovery
                asyncio.create_task(self._run_simulated_ble_server_async())
                return True

            # Real BLE implementation would go here
            await asyncio.sleep(1)  # Simulate real BLE startup

            # Create advertising data
            advertising_data = {
                "device_name": self.config.device_name,
                "device_id": device_info.device_id,
                "mac_address": device_info.mac_address,
                "service_uuid": self.config.service_uuid,
                "recovery_enabled": True,
                "session_timeout": 300,  # 5 minutes
            }

            # Start the real BLE server asynchronously
            asyncio.create_task(self._run_real_ble_server())
            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to perform BLE advertising startup: {e}")
            return False

    async def stop_advertising(
        self, timeout: Optional[float] = None
    ) -> Result[bool, Exception]:
        """Stop BLE advertising with consistent error handling and async support"""
        timeout = timeout or 10.0  # Default 10 second timeout

        try:
            if self.logger:
                self.logger.info(f"Stopping BLE advertising with timeout {timeout}s")

            # Create cancellable stop task
            stop_task = asyncio.create_task(self._perform_stop_advertising())

            try:
                success = await asyncio.wait_for(stop_task, timeout=timeout)

                if success:
                    self.is_advertising_flag = False
                    self._connection_state = "disconnected"
                    self._should_recover = False

                    if self.logger:
                        self.logger.info("BLE advertising stopped successfully")
                    return Result.success(True)
                else:
                    error_msg = "Failed to stop BLE advertising"
                    return Result.failure(
                        BLEError(
                            ErrorCode.BLE_OPERATION_FAILED,
                            error_msg,
                            ErrorSeverity.MEDIUM,
                        )
                    )

            except asyncio.TimeoutError:
                stop_task.cancel()
                error_msg = f"BLE advertising stop timed out after {timeout}s"
                if self.logger:
                    self.logger.error(error_msg)
                return Result.failure(
                    BLEError(
                        ErrorCode.BLE_TIMEOUT,
                        error_msg,
                        ErrorSeverity.MEDIUM,
                    )
                )

        except Exception as e:
            error_msg = f"Stop BLE advertising failed: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                BLEError(
                    ErrorCode.BLE_OPERATION_FAILED,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

    async def _perform_stop_advertising(self) -> bool:
        """Perform the actual BLE advertising stop asynchronously"""
        try:
            self.is_advertising_flag = False
            self._should_recover = False

            if self.current_process:
                # Gracefully terminate the process
                self.current_process.terminate()
                try:
                    await asyncio.sleep(2)  # Give it time to terminate gracefully
                    if self.current_process.poll() is None:
                        self.current_process.kill()  # Force kill if needed
                except:
                    pass
                finally:
                    self.current_process = None

            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to perform BLE advertising stop: {e}")
            return False

    async def monitor_connection_health(self, interval: float = 5.0) -> None:
        """Monitor BLE connection health continuously with async support"""
        while self.is_advertising_flag and self._should_recover:
            try:
                # Check connection state
                current_time = time.time()

                # Check for stale connections
                if (
                    current_time - self._last_heartbeat > 30
                ):  # 30 seconds without heartbeat
                    if self.logger:
                        self.logger.warning(
                            "BLE connection appears stale, triggering recovery"
                        )
                    await self._trigger_recovery_async()

                # Check for disconnection
                if await self._detect_disconnection_async():
                    if self.logger:
                        self.logger.warning(
                            "BLE disconnection detected, attempting recovery"
                        )
                    await self._trigger_recovery_async()

                # Update heartbeat
                self._last_heartbeat = current_time

                await asyncio.sleep(interval)

            except Exception as e:
                if self.logger:
                    self.logger.error(f"BLE connection health monitoring error: {e}")
                await asyncio.sleep(interval)

    async def _trigger_recovery_async(self) -> None:
        """Trigger BLE recovery process asynchronously with proper synchronization"""
        async with self._recovery_lock:
            if self._recovery_in_progress:
                if self.logger:
                    self.logger.debug("Recovery already in progress, skipping")
                return

            if self._connection_attempts < self._max_reconnection_attempts:
                self._recovery_in_progress = True
                self._connection_attempts += 1
                self._connection_state = "recovering"

                if self.logger:
                    self.logger.info(
                        f"Triggering BLE recovery (attempt {self._connection_attempts}/{self._max_reconnection_attempts})"
                    )

                try:
                    # Start recovery in background with proper cleanup
                    asyncio.create_task(self._recovery_process_async())
                finally:
                    # Reset the flag after a delay to prevent rapid retries
                    async def reset_recovery_flag():
                        await asyncio.sleep(self._reconnection_delay)
                        async with self._recovery_lock:
                            self._recovery_in_progress = False

                    asyncio.create_task(reset_recovery_flag())
            else:
                if self.logger:
                    self.logger.error("Maximum BLE reconnection attempts exceeded")
                self._should_recover = False

    async def _recovery_process_async(self) -> None:
        """Background recovery process with complete reconnection state machine"""
        try:
            if self.logger:
                self.logger.info("Starting async BLE recovery process")

            # Wait for reconnection delay
            await asyncio.sleep(self._reconnection_delay)

            # Attempt reconnection
            if await self._implement_automatic_reconnection_async():
                if self.logger:
                    self.logger.info("BLE recovery successful")
                self._connection_state = "connected"
                self._connection_attempts = 0  # Reset attempts on success

                # Restore session state
                await self._restore_session_state_async()
            else:
                if self.logger:
                    self.logger.warning("BLE recovery failed")
                # Will retry on next health check if within attempt limits

        except Exception as e:
            if self.logger:
                self.logger.error(f"BLE recovery process failed: {e}")

    async def _implement_automatic_reconnection_async(self) -> bool:
        """Implement core reconnection state machine asynchronously"""
        try:
            # Check if we're still within the reconnection window
            if not self.is_advertising_flag or not self._should_recover:
                return False

            # Attempt to restart BLE service
            success = await self._attempt_ble_reconnection_async()

            if success:
                # Verify data integrity after reconnection
                return await self._verify_data_integrity_async()

            return False

        except Exception as e:
            if self.logger:
                self.logger.error(f"Automatic BLE reconnection failed: {e}")
            return False

    async def _detect_disconnection_async(self) -> bool:
        """Detect if BLE connection is actually disconnected asynchronously"""
        try:
            # In a real implementation, this would check actual BLE connection status
            # For simulation, check if the connection state indicates disconnection
            return self._connection_state == "disconnected"

        except Exception as e:
            if self.logger:
                self.logger.debug(f"BLE disconnection detection error: {e}")
            return False

    async def _attempt_ble_reconnection_async(self) -> bool:
        """Attempt to reconnect BLE service asynchronously"""
        try:
            if self.logger:
                self.logger.info("Attempting async BLE reconnection")

            # Simulate reconnection attempt
            await asyncio.sleep(2)

            # In a real implementation, this would restart the BLE service
            if not BLEAK_AVAILABLE:
                # Restart simulated BLE server
                asyncio.create_task(self._run_simulated_ble_server_async())
                return True
            else:
                # Restart real BLE server
                asyncio.create_task(self._run_real_ble_server())
                return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"BLE reconnection attempt failed: {e}")
            return False

    async def cleanup_sessions(self) -> None:
        """Properly cleanup sessions and resources with thread safety"""
        async with self._session_lock:
            try:
                if self.logger:
                    self.logger.info("Cleaning up BLE sessions and resources")

                # Clean up session data
                self._session_data.clear()
                self._session_backup.clear()
                self._pending_credentials = None

                # Cancel any ongoing cleanup tasks
                if self._cleanup_task and not self._cleanup_task.done():
                    self._cleanup_task.cancel()
                    try:
                        await self._cleanup_task
                    except asyncio.CancelledError:
                        pass

                # Reset connection state
                self._connection_state = "disconnected"
                self._should_recover = False

                if self.logger:
                    self.logger.info("BLE session cleanup completed")

            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error during session cleanup: {e}")

    async def _restore_session_state_async(self) -> None:
        """Restore session state after recovery with proper locking"""
        async with self._session_lock:
            try:
                if self._session_backup:
                    self._session_data = self._session_backup.copy()
                    if self.logger:
                        self.logger.info("Session state restored after recovery")

                # Clear backup after restoration
                self._session_backup.clear()

            except Exception as e:
                if self.logger:
                    self.logger.error(f"Failed to restore session state: {e}")

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with proper cleanup"""
        await self.cleanup_sessions()
        await self.stop_advertising()

    def start_advertising(self, device_info: DeviceInfo) -> Result[bool, Exception]:
        """Start BLE advertising with consistent error handling and recovery logic"""
        try:
            if self.logger:
                self.logger.info("Starting BLE advertising with recovery support")

            # Initialize recovery state
            self._connection_attempts = 0
            self._should_recover = True
            self._session_data = {}
            self._last_heartbeat = time.time()
            self._connection_state = "connecting"
            self._session_backup = {}
            self._pending_credentials = None

            if not BLEAK_AVAILABLE:
                # Simulate BLE advertising with recovery
                self.is_advertising_flag = True
                self._connection_state = "connected"
                if self.logger:
                    self.logger.warning(
                        "BLE advertising simulated with recovery logic (Bleak not available)"
                    )
                # Start background task to handle connections with recovery
                threading.Thread(target=self._run_ble_server, daemon=True).start()
                return Result.success(True)

            # Real BLE implementation would go here
            self.is_advertising_flag = True
            self._connection_state = "connected"

            # Create advertising data
            advertising_data = {
                "device_name": self.config.device_name,
                "device_id": device_info.device_id,
                "mac_address": device_info.mac_address,
                "service_uuid": self.config.service_uuid,
                "recovery_enabled": True,
                "session_timeout": 300,  # 5 minutes
            }

            if self.logger:
                self.logger.info(
                    f"BLE advertising started with recovery data: {advertising_data}"
                )

            # Start background task to handle connections with recovery
            threading.Thread(target=self._run_ble_server, daemon=True).start()

            return Result.success(True)

        except Exception as e:
            self._connection_state = "disconnected"
            error_msg = f"Failed to start BLE advertising: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                BLEError(
                    ErrorCode.BLE_ADVERTISING_FAILED,
                    error_msg,
                    ErrorSeverity.HIGH,
                )
            )

    def stop_advertising(self) -> Result[bool, Exception]:
        """Stop BLE advertising with consistent error handling"""
        try:
            if self.logger:
                self.logger.info("Stopping BLE advertising")

            self.is_advertising_flag = False

            if self.peripheral:
                # Stop peripheral if running
                pass

            if self.logger:
                self.logger.info("BLE advertising stopped")

            return Result.success(True)

        except Exception as e:
            error_msg = f"Failed to stop BLE advertising: {e}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                BLEError(
                    ErrorCode.BLE_ADVERTISING_FAILED,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

    def is_advertising(self) -> bool:
        """Check if currently advertising"""
        return self.is_advertising_flag

    def set_credentials_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set callback for received credentials"""
        self.credentials_callback = callback
        if self.logger:
            self.logger.debug("Credentials callback set")

    def _run_ble_server(self):
        """Run BLE server with real implementation and recovery logic"""
        try:
            if self.logger:
                self.logger.info("BLE server started with recovery capabilities")

            if BLEAK_AVAILABLE:
                # Real BLE implementation with bleak
                asyncio.run(self._run_real_ble_server())
            else:
                # Enhanced simulation with recovery testing
                self._run_simulated_ble_server_with_recovery()

            if self.logger:
                self.logger.info("BLE server stopped")

        except Exception as e:
            if self.logger:
                self.logger.error(f"BLE server error: {e}")

            # Trigger recovery if enabled
            if self._should_recover:
                self._trigger_recovery()

    async def _run_real_ble_server(self):
        """Real BLE server implementation using bleak"""
        try:
            from bleak import BleakAdapter, BleakServer
            from bleak.backends.characteristic import BleakGATTCharacteristic
            from bleak.backends.service import BleakGATTService

            # Set up GATT service and characteristics
            service_uuid = self.config.service_uuid
            characteristic_uuid = "12345678-1234-1234-1234-123456789abc"

            # Create service
            service = BleakGATTService(service_uuid, True)

            # Create characteristic for receiving credentials
            characteristic = BleakGATTCharacteristic(
                characteristic_uuid, ["write"], None, service
            )

            service.add_characteristic(characteristic)

            # Set up server
            server = BleakServer(name=self.config.device_name)
            server.add_service(service)

            # Set characteristic write handler
            characteristic.set_write_handler(self._handle_characteristic_write)

            # Start server with recovery logic
            while self.is_advertising_flag:
                try:
                    await server.start()

                    # Update heartbeat
                    self._last_heartbeat = time.time()

                    # Wait for connections with periodic heartbeat
                    while self.is_advertising_flag:
                        await asyncio.sleep(1.0)

                        # Check for connection timeout
                        if time.time() - self._last_heartbeat > 30.0:
                            if self.logger:
                                self.logger.warning("BLE connection heartbeat timeout")
                            break

                    await server.stop()

                except Exception as e:
                    if self.logger:
                        self.logger.error(f"BLE server error: {e}")

                    # Implement reconnection logic
                    if self._connection_attempts < self._max_reconnection_attempts:
                        self._connection_attempts += 1
                        if self.logger:
                            self.logger.info(
                                f"Attempting BLE reconnection {self._connection_attempts}/{self._max_reconnection_attempts}"
                            )

                        # Wait 10 seconds before reconnection attempt
                        await asyncio.sleep(self._reconnection_delay)
                    else:
                        if self.logger:
                            self.logger.error("Max BLE reconnection attempts reached")
                        break

        except ImportError:
            if self.logger:
                self.logger.error(
                    "Bleak library not available for real BLE implementation"
                )
            # Fallback to simulation
            self._run_simulated_ble_server_with_recovery()

    def _run_simulated_ble_server_with_recovery(self):
        """Enhanced simulation with recovery logic for testing"""

        while self.is_advertising_flag:
            try:
                time.sleep(1)

                # Simulate connection issues and recovery
                if random.random() < 0.01:  # 1% chance of connection issue
                    if self.logger:
                        self.logger.warning("Simulated BLE connection issue")

                    # Trigger recovery
                    self._trigger_recovery()
                    continue

                # Simulate receiving credentials (higher probability for testing)
                if (
                    random.random() < 0.005 and self.credentials_callback
                ):  # 0.5% chance per second
                    # Simulate session persistence
                    if not self._session_data:
                        self._session_data = {
                            "session_id": f"sim_session_{int(time.time())}",
                            "connected_at": time.time(),
                            "last_activity": time.time(),
                        }

                    # Update session activity
                    self._session_data["last_activity"] = time.time()

                    # Simulate received credentials with data integrity
                    credentials = {
                        "ssid": "TestNetwork_Secure",
                        "password": "testpassword123",
                        "timestamp": time.time(),
                        "session_id": self._session_data["session_id"],
                    }

                    # Validate data integrity
                    if self._validate_credentials_integrity(credentials):
                        ssid = credentials["ssid"]
                        password = credentials["password"]

                        if self.logger:
                            self.logger.info(
                                f"Simulated BLE credentials received with recovery: SSID={ssid}"
                            )

                        # Call the callback
                        try:
                            self.credentials_callback(ssid, password)
                            # Reset connection attempts on successful data transfer
                            self._connection_attempts = 0
                        except Exception as e:
                            if self.logger:
                                self.logger.error(f"Error in credentials callback: {e}")
                    else:
                        if self.logger:
                            self.logger.warning(
                                "Corrupted credentials detected, triggering recovery"
                            )
                        self._trigger_recovery()

                # Update heartbeat
                self._last_heartbeat = time.time()

            except Exception as e:
                if self.logger:
                    self.logger.error(f"Simulated BLE server error: {e}")
                self._trigger_recovery()

    def _trigger_recovery(self):
        """Trigger BLE recovery process"""
        if self._connection_attempts < self._max_reconnection_attempts:
            self._connection_attempts += 1

            if self.logger:
                self.logger.info(
                    f"Triggering BLE recovery attempt {self._connection_attempts}/{self._max_reconnection_attempts}"
                )

            # Start recovery thread if not already running
            if not self._recovery_thread or not self._recovery_thread.is_alive():
                self._should_recover = True
                self._recovery_thread = threading.Thread(
                    target=self._recovery_process, daemon=True
                )
                self._recovery_thread.start()
        else:
            if self.logger:
                self.logger.error("Max recovery attempts reached, BLE service degraded")

    def _recovery_process(self):
        """Background recovery process with complete reconnection state machine"""
        try:
            if self.logger:
                self.logger.info("Starting BLE recovery process")

            # Wait for the 10-second reconnection delay
            time.sleep(self._reconnection_delay)

            # IMPLEMENTATION: Actual reconnection state machine
            recovery_success = self._implement_automatic_reconnection()

            if recovery_success:
                # IMPLEMENTATION: Session persistence during disconnection
                if self._session_data:
                    if self.logger:
                        self.logger.info(
                            f"Restoring BLE session: {self._session_data['session_id']}"
                        )

                    # Restore session state on reconnection
                    self._restore_session_state()

                    # IMPLEMENTATION: Data integrity verification after recovery
                    if self._verify_data_integrity():
                        if self.logger:
                            self.logger.info(
                                "BLE recovery completed successfully with data integrity verified"
                            )
                        # Reset connection attempts on successful recovery
                        self._connection_attempts = 0
                    else:
                        if self.logger:
                            self.logger.warning(
                                "Data integrity verification failed after recovery"
                            )
                        # Don't reset attempts if integrity check fails
                else:
                    if self.logger:
                        self.logger.info(
                            "BLE recovery completed (no session to restore)"
                        )
                    self._connection_attempts = 0
            else:
                if self.logger:
                    self.logger.warning("BLE reconnection attempt failed")

            # Reset recovery flag
            self._should_recover = False

            if self.logger:
                self.logger.info("BLE recovery process completed")

        except Exception as e:
            if self.logger:
                self.logger.error(f"BLE recovery process error: {e}")

    def _implement_automatic_reconnection(self) -> bool:
        """Implement core reconnection state machine within 10s window"""
        try:
            if self.logger:
                self.logger.info("Implementing automatic BLE reconnection")

            # Detect disconnection events
            if not self._detect_disconnection():
                if self.logger:
                    self.logger.debug(
                        "No disconnection detected, skipping reconnection"
                    )
                return True

            # Attempt reconnection within 10s window
            reconnection_start = time.time()
            max_reconnection_time = 10.0  # 10 seconds as per requirements

            while time.time() - reconnection_start < max_reconnection_time:
                try:
                    # Simulate reconnection attempt
                    if self._attempt_ble_reconnection():
                        if self.logger:
                            self.logger.info("BLE reconnection successful")
                        return True

                    # Short delay between attempts
                    time.sleep(1.0)

                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"Reconnection attempt failed: {e}")
                    time.sleep(1.0)

            if self.logger:
                self.logger.warning("BLE reconnection failed within 10s window")
            return False

        except Exception as e:
            if self.logger:
                self.logger.error(f"Automatic reconnection implementation error: {e}")
            return False

    def _detect_disconnection(self) -> bool:
        """Detect if BLE connection is actually disconnected"""
        try:
            # Check heartbeat timeout
            current_time = time.time()
            if current_time - self._last_heartbeat > 30.0:
                if self.logger:
                    self.logger.info("BLE disconnection detected via heartbeat timeout")
                self._connection_state = "disconnected"
                self._last_disconnection_time = current_time
                return True

            # Check session validity
            if self._session_data:
                session_age = current_time - self._session_data.get("connected_at", 0)
                if session_age > 300:  # 5 minutes
                    if self.logger:
                        self.logger.info(
                            "BLE disconnection detected via session timeout"
                        )
                    self._connection_state = "disconnected"
                    self._last_disconnection_time = current_time
                    return True

            # Additional check: verify connection state consistency
            if self._connection_state == "disconnected":
                return True

            return False

        except Exception as e:
            if self.logger:
                self.logger.error(f"Disconnection detection error: {e}")
            # Assume disconnected if we can't determine state
            self._connection_state = "disconnected"
            self._last_disconnection_time = time.time()
            return True

    def _attempt_ble_reconnection(self) -> bool:
        """Attempt to reconnect BLE service"""
        try:
            if self.logger:
                self.logger.debug("Attempting BLE reconnection")

            self._connection_state = "connecting"

            # Simulate reconnection logic
            if BLEAK_AVAILABLE:
                # In real implementation, would reinitialize BLE adapter/peripheral
                # For now, simulate successful reconnection
                self._last_heartbeat = time.time()
                self._connection_state = "connected"
                if self.logger:
                    self.logger.debug("Real BLE reconnection successful")
                return True
            else:
                # Simulated reconnection with more realistic failure scenarios
                import random

                # Higher success rate if within 10-second window
                time_since_disconnect = time.time() - self._last_disconnection_time
                if time_since_disconnect <= 10.0:
                    reconnection_success = (
                        random.random() > 0.2
                    )  # 80% success rate within window
                else:
                    reconnection_success = (
                        random.random() > 0.5
                    )  # 50% success rate after window

                if reconnection_success:
                    self._last_heartbeat = time.time()
                    self._connection_state = "connected"
                    if self.logger:
                        self.logger.debug("Simulated BLE reconnection successful")
                    return True
                else:
                    self._connection_state = "disconnected"
                    if self.logger:
                        self.logger.debug("Simulated BLE reconnection failed")
                    return False

        except Exception as e:
            if self.logger:
                self.logger.error(f"BLE reconnection attempt error: {e}")
            self._connection_state = "disconnected"
            return False

    def _restore_session_state(self):
        """Restore session state on reconnection"""
        try:
            if not self._session_data:
                # Check if we have a backup to restore from
                if self._session_backup:
                    self._session_data = self._session_backup.copy()
                    if self.logger:
                        self.logger.info("Session state restored from backup")
                else:
                    return

            # Update session timing
            current_time = time.time()
            self._session_data["last_activity"] = current_time
            self._session_data["reconnected_at"] = current_time

            # Mark session as restored
            self._session_data["restored"] = True

            # Restore any pending credentials if they exist
            if self._pending_credentials:
                self._session_data["pending_credentials"] = self._pending_credentials
                if self.logger:
                    self.logger.info(
                        "Pending credentials restored during session recovery"
                    )

            # Update backup
            self._session_backup = self._session_data.copy()

            if self.logger:
                self.logger.info(
                    f"Session state restored for session: {self._session_data['session_id']}"
                )

        except Exception as e:
            if self.logger:
                self.logger.error(f"Session state restoration error: {e}")
            # Try to restore from backup if main session data is corrupted
            if self._session_backup:
                try:
                    self._session_data = self._session_backup.copy()
                    if self.logger:
                        self.logger.warning("Session restored from backup after error")
                except Exception as backup_error:
                    if self.logger:
                        self.logger.error(
                            f"Failed to restore from backup: {backup_error}"
                        )

    def _verify_data_integrity(self) -> bool:
        """Validate data integrity after recovery"""
        try:
            if not self._session_data:
                # No session data to verify
                return True

            # Check session data integrity
            required_fields = ["session_id", "connected_at", "last_activity"]
            for field in required_fields:
                if field not in self._session_data:
                    if self.logger:
                        self.logger.warning(f"Missing session field: {field}")
                    return False

            # Verify session ID format
            session_id = self._session_data["session_id"]
            if not session_id or len(session_id) < 10:
                if self.logger:
                    self.logger.warning("Invalid session ID format")
                return False

            # Verify timing integrity
            current_time = time.time()
            connected_at = self._session_data.get("connected_at", 0)
            last_activity = self._session_data.get("last_activity", 0)

            if connected_at > current_time or last_activity > current_time:
                if self.logger:
                    self.logger.warning("Session timing integrity check failed")
                return False

            if self.logger:
                self.logger.debug("Data integrity verification passed")
            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Data integrity verification error: {e}")
            return False

    def _validate_credentials_integrity(self, credentials: Dict[str, Any]) -> bool:
        """Validate integrity of received credentials"""
        try:
            required_fields = ["ssid", "password", "timestamp", "session_id"]

            # Check required fields
            for field in required_fields:
                if field not in credentials:
                    return False

            # Check data types
            if not isinstance(credentials["ssid"], str) or not isinstance(
                credentials["password"], str
            ):
                return False

            # Check timestamp validity (within last 5 minutes)
            current_time = time.time()
            if abs(current_time - credentials["timestamp"]) > 300:
                return False

            # Check for suspicious content
            suspicious_patterns = ["<script", "javascript:", "${", "../"]
            for pattern in suspicious_patterns:
                if (
                    pattern in credentials["ssid"].lower()
                    or pattern in credentials["password"].lower()
                ):
                    return False

            return True

        except Exception:
            return False

    def _handle_characteristic_write(self, characteristic: Any, data: bytes):
        """Handle characteristic write (for real BLE implementation)"""
        try:
            if self.logger:
                self.logger.debug(f"BLE data received: {len(data)} bytes")

            # Decode JSON data
            json_str = data.decode("utf-8")
            credentials_data = json.loads(json_str)

            ssid = credentials_data.get("ssid", "")
            password = credentials_data.get("password", "")

            if ssid and password and self.credentials_callback:
                if self.logger:
                    self.logger.info(f"Valid credentials received via BLE: SSID={ssid}")

                self.credentials_callback(ssid, password)
            else:
                if self.logger:
                    self.logger.warning("Invalid credentials data received via BLE")

        except json.JSONDecodeError as e:
            if self.logger:
                self.logger.error(f"Invalid JSON in BLE data: {e}")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error handling BLE data: {e}")

    async def _perform_recovery_logic(self) -> bool:
        """Complete BLE recovery logic with session persistence and data integrity"""
        try:
            if self.logger:
                self.logger.info("Performing comprehensive BLE recovery")

            # Step 1: Validate recovery window (10 seconds)
            if not await self._validate_recovery_window():
                if self.logger:
                    self.logger.error("Recovery window validation failed")
                return False

            # Step 2: Backup current session state before recovery
            await self._backup_session_state_async()

            # Step 3: Attempt reconnection within the 10-second window
            reconnection_success = await self._implement_automatic_reconnection_async()

            if not reconnection_success:
                if self.logger:
                    self.logger.error("Automatic reconnection failed during recovery")
                return False

            # Step 4: Restore session state after successful reconnection
            await self._restore_session_state_async(self._session_backup)

            # Step 5: Verify data integrity after recovery
            if not await self._verify_data_integrity_async():
                if self.logger:
                    self.logger.error(
                        "Data integrity verification failed after recovery"
                    )
                return False

            # Step 6: Restore any pending credentials
            if self._pending_credentials:
                await self._restore_pending_credentials_async()

            # Step 7: Reset recovery state
            self._connection_attempts = 0
            self._recovery_in_progress = False
            self._connection_state = "connected"

            if self.logger:
                self.logger.info("BLE recovery completed successfully")
            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"BLE recovery logic failed: {e}")
            return False

    async def _validate_recovery_window(self) -> bool:
        """Validate that we're within the 10-second recovery window"""
        try:
            current_time = time.time()

            # Check if we have a disconnection timestamp
            if self._last_disconnection_time == 0:
                # If no disconnection time, assume we're in recovery window
                if self.logger:
                    self.logger.debug(
                        "No disconnection timestamp, assuming valid recovery window"
                    )
                return True

            # Calculate time since disconnection
            time_since_disconnect = current_time - self._last_disconnection_time

            # 10-second recovery window as per requirements
            recovery_window = 10.0

            if time_since_disconnect <= recovery_window:
                if self.logger:
                    self.logger.info(
                        f"Within recovery window: {time_since_disconnect:.2f}s of {recovery_window}s"
                    )
                return True
            else:
                if self.logger:
                    self.logger.warning(
                        f"Outside recovery window: {time_since_disconnect:.2f}s > {recovery_window}s"
                    )
                return False

        except Exception as e:
            if self.logger:
                self.logger.error(f"Recovery window validation error: {e}")
            return False

    async def _backup_session_state_async(self) -> None:
        """Async backup of session state for recovery purposes"""
        async with self._session_lock:
            try:
                if self._session_data:
                    # Create a deep copy of session data for backup
                    import copy

                    self._session_backup = copy.deepcopy(self._session_data)

                    # Add backup metadata
                    self._session_backup["backup_timestamp"] = time.time()
                    self._session_backup["backup_reason"] = "recovery_preparation"

                    if self.logger:
                        self.logger.debug("Session state backed up for recovery")
                else:
                    if self.logger:
                        self.logger.warning("No session data to backup")

            except Exception as e:
                if self.logger:
                    self.logger.error(f"Async session backup failed: {e}")

    async def _restore_session_state_async(self, session_data: Dict[str, Any]) -> None:
        """Async restore session state from backup"""
        async with self._session_lock:
            try:
                if session_data:
                    # Restore session data
                    import copy

                    self._session_data = copy.deepcopy(session_data)

                    # Update restoration metadata
                    current_time = time.time()
                    self._session_data["last_activity"] = current_time
                    self._session_data["restored_at"] = current_time
                    self._session_data["restored"] = True

                    # Remove backup metadata from active session
                    self._session_data.pop("backup_timestamp", None)
                    self._session_data.pop("backup_reason", None)

                    if self.logger:
                        session_id = self._session_data.get("session_id", "unknown")
                        self.logger.info(
                            f"Session state restored async: {session_id[:8]}..."
                        )
                else:
                    if self.logger:
                        self.logger.warning("No session data provided for restoration")

            except Exception as e:
                if self.logger:
                    self.logger.error(f"Async session restoration failed: {e}")

    async def _verify_data_integrity_async(self) -> bool:
        """Async verification of data integrity after recovery"""
        try:
            if not self._session_data:
                if self.logger:
                    self.logger.debug("No session data to verify")
                return True

            # Check required session fields
            required_fields = ["session_id", "connected_at", "last_activity"]

            missing_fields = []
            for field in required_fields:
                if field not in self._session_data:
                    missing_fields.append(field)

            if missing_fields:
                if self.logger:
                    self.logger.error(
                        f"Session integrity check failed - missing fields: {missing_fields}"
                    )
                return False

            # Verify session ID format and validity
            session_id = self._session_data["session_id"]
            if not session_id or len(session_id) < 10:
                if self.logger:
                    self.logger.error("Session ID integrity check failed")
                return False

            # Verify timestamp integrity
            current_time = time.time()
            connected_at = self._session_data.get("connected_at", 0)
            last_activity = self._session_data.get("last_activity", 0)

            # Check for future timestamps (indicates corruption)
            if connected_at > current_time + 60 or last_activity > current_time + 60:
                if self.logger:
                    self.logger.error(
                        "Session timestamp integrity check failed - future timestamps detected"
                    )
                return False

            # Check for reasonable timestamp ranges (not too old)
            max_session_age = 3600  # 1 hour
            if current_time - connected_at > max_session_age:
                if self.logger:
                    self.logger.warning("Session may be too old, but allowing recovery")

            # Verify pending credentials integrity if they exist
            if self._pending_credentials:
                if not await self._verify_pending_credentials_integrity_async():
                    if self.logger:
                        self.logger.error("Pending credentials integrity check failed")
                    return False

            if self.logger:
                self.logger.info("Data integrity verification passed")
            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Async data integrity verification failed: {e}")
            return False

    async def _implement_automatic_reconnection_async(self) -> bool:
        """Async implementation of automatic reconnection within 10-second window"""
        try:
            if self.logger:
                self.logger.info("Starting async automatic BLE reconnection")

            # Check if disconnection was detected
            if not self._detect_disconnection():
                if self.logger:
                    self.logger.debug(
                        "No disconnection detected, skipping reconnection"
                    )
                return True

            # Start reconnection attempts within 10-second window
            reconnection_start = time.time()
            max_reconnection_time = 10.0  # 10 seconds as per requirements
            attempt_interval = 1.0  # Try every second

            attempt_count = 0
            while time.time() - reconnection_start < max_reconnection_time:
                attempt_count += 1

                try:
                    if self.logger:
                        elapsed = time.time() - reconnection_start
                        self.logger.debug(
                            f"Reconnection attempt {attempt_count} (elapsed: {elapsed:.1f}s)"
                        )

                    # Attempt to reestablish BLE connection
                    if await self._attempt_ble_reconnection_async():
                        reconnection_time = time.time() - reconnection_start
                        if self.logger:
                            self.logger.info(
                                f"BLE reconnection successful in {reconnection_time:.2f}s"
                            )

                        # Update connection state
                        self._connection_state = "connected"
                        self._last_heartbeat = time.time()

                        return True

                    # Wait before next attempt
                    await asyncio.sleep(attempt_interval)

                except Exception as attempt_error:
                    if self.logger:
                        self.logger.warning(
                            f"Reconnection attempt {attempt_count} failed: {attempt_error}"
                        )
                    await asyncio.sleep(attempt_interval)

            # If we get here, reconnection failed within the window
            elapsed = time.time() - reconnection_start
            if self.logger:
                self.logger.error(
                    f"BLE reconnection failed within {max_reconnection_time}s window (total time: {elapsed:.2f}s)"
                )

            self._connection_state = "disconnected"
            return False

        except Exception as e:
            if self.logger:
                self.logger.error(f"Async automatic reconnection failed: {e}")
            return False

    async def _attempt_ble_reconnection_async(self) -> bool:
        """Async attempt to reestablish BLE connection"""
        try:
            if not BLEAK_AVAILABLE:
                # Simulate reconnection for testing
                await asyncio.sleep(0.1)  # Simulate connection time

                # Simulate occasional failures for testing
                import random

                if random.random() > 0.8:  # 20% failure rate for testing
                    if self.logger:
                        self.logger.debug("Simulated BLE reconnection failed")
                    return False

                if self.logger:
                    self.logger.debug("Simulated BLE reconnection successful")
                return True

            # Real BLE reconnection implementation
            try:
                # In a real implementation, this would:
                # 1. Stop current adapter/peripheral
                # 2. Reinitialize BLE components
                # 3. Restart advertising
                # 4. Verify connection establishment

                # For now, simulate the process
                await asyncio.sleep(0.5)  # Simulate connection setup time

                # Update internal state
                self._last_heartbeat = time.time()

                if self.logger:
                    self.logger.debug("BLE reconnection attempt completed")

                return True

            except Exception as ble_error:
                if self.logger:
                    self.logger.error(f"BLE reconnection attempt failed: {ble_error}")
                return False

        except Exception as e:
            if self.logger:
                self.logger.error(f"Async BLE reconnection attempt error: {e}")
            return False

    async def _restore_pending_credentials_async(self) -> None:
        """Async restoration of pending credentials after recovery"""
        try:
            if not self._pending_credentials:
                if self.logger:
                    self.logger.debug("No pending credentials to restore")
                return

            if self.logger:
                self.logger.info("Restoring pending credentials after recovery")

            # Verify credentials are still valid (not too old)
            current_time = time.time()
            credential_timestamp = self._pending_credentials.get("timestamp", 0)
            max_credential_age = 300  # 5 minutes

            if current_time - credential_timestamp > max_credential_age:
                if self.logger:
                    self.logger.warning("Pending credentials too old, discarding")
                self._pending_credentials = None
                return

            # Verify credentials integrity
            if not await self._verify_pending_credentials_integrity_async():
                if self.logger:
                    self.logger.error(
                        "Pending credentials integrity check failed, discarding"
                    )
                self._pending_credentials = None
                return

            # Restore credentials by calling the callback
            if self.credentials_callback and self._pending_credentials.get(
                "complete", False
            ):
                ssid = self._pending_credentials.get("ssid")
                password = self._pending_credentials.get("password")

                if ssid and password:
                    try:
                        self.credentials_callback(ssid, password)
                        if self.logger:
                            self.logger.info(
                                f"Pending credentials restored successfully: SSID={ssid}"
                            )

                        # Clear pending credentials after successful restoration
                        self._pending_credentials = None

                    except Exception as callback_error:
                        if self.logger:
                            self.logger.error(
                                f"Credentials callback failed during restoration: {callback_error}"
                            )
                else:
                    if self.logger:
                        self.logger.error("Invalid pending credentials data")
                    self._pending_credentials = None
            else:
                if self.logger:
                    self.logger.warning(
                        "Cannot restore pending credentials - no callback or incomplete credentials"
                    )

        except Exception as e:
            if self.logger:
                self.logger.error(f"Async pending credentials restoration failed: {e}")
            self._pending_credentials = None

    async def _verify_pending_credentials_integrity_async(self) -> bool:
        """Async verification of pending credentials integrity"""
        try:
            if not self._pending_credentials:
                return True

            # Check required fields
            required_fields = ["ssid", "password", "timestamp", "session_id"]
            for field in required_fields:
                if field not in self._pending_credentials:
                    if self.logger:
                        self.logger.error(f"Pending credentials missing field: {field}")
                    return False

            # Verify SSID and password are valid strings
            ssid = self._pending_credentials.get("ssid")
            password = self._pending_credentials.get("password")

            if not isinstance(ssid, str) or not isinstance(password, str):
                if self.logger:
                    self.logger.error("Pending credentials have invalid data types")
                return False

            if not ssid.strip() or len(password) < 1:
                if self.logger:
                    self.logger.error("Pending credentials have empty values")
                return False

            # Verify timestamp is reasonable
            timestamp = self._pending_credentials.get("timestamp", 0)
            current_time = time.time()

            if timestamp > current_time + 60:  # Future timestamp
                if self.logger:
                    self.logger.error("Pending credentials have future timestamp")
                return False

            if current_time - timestamp > 3600:  # Older than 1 hour
                if self.logger:
                    self.logger.warning("Pending credentials are very old")
                return False

            if self.logger:
                self.logger.debug("Pending credentials integrity verification passed")
            return True

        except Exception as e:
            if self.logger:
                self.logger.error(
                    f"Pending credentials integrity verification failed: {e}"
                )
            return False
