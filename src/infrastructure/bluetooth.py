"""
Bluetooth service implementation
"""

import asyncio
import json
import threading
from typing import Any, Callable, Dict, Optional

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
    """Concrete implementation of Bluetooth service"""

    def __init__(self, config: BLEConfig, logger: Optional[ILogger] = None):
        self.config = config
        self.logger = logger
        self.is_advertising_flag = False
        self.credentials_callback: Optional[Callable[[str, str], None]] = None
        self.peripheral: Optional[Any] = None
        self.adapter: Optional[Any] = None

        if not BLEAK_AVAILABLE:
            if self.logger:
                self.logger.warning(
                    "Bleak library not available, BLE functionality will be simulated"
                )

    def start_advertising(self, device_info: DeviceInfo) -> bool:
        """Start BLE advertising"""
        try:
            if self.logger:
                self.logger.info("Starting BLE advertising")

            if not BLEAK_AVAILABLE:
                # Simulate BLE advertising
                self.is_advertising_flag = True
                if self.logger:
                    self.logger.warning(
                        "BLE advertising simulated (Bleak not available)"
                    )
                return True

            # Real BLE implementation would go here
            # For now, we'll simulate it
            self.is_advertising_flag = True

            # Create advertising data
            advertising_data = {
                "device_name": self.config.device_name,
                "device_id": device_info.device_id,
                "mac_address": device_info.mac_address,
                "service_uuid": self.config.service_uuid,
            }

            if self.logger:
                self.logger.info(
                    f"BLE advertising started with data: {advertising_data}"
                )

            # Start background task to handle connections
            threading.Thread(target=self._run_ble_server, daemon=True).start()

            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to start BLE advertising: {e}")
            raise BLEError(
                ErrorCode.BLE_ADVERTISING_FAILED,
                f"Failed to start BLE advertising: {str(e)}",
                ErrorSeverity.HIGH,
            )

    def stop_advertising(self) -> bool:
        """Stop BLE advertising"""
        try:
            if self.logger:
                self.logger.info("Stopping BLE advertising")

            self.is_advertising_flag = False

            if self.peripheral:
                # Stop peripheral if running
                pass

            if self.logger:
                self.logger.info("BLE advertising stopped")

            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to stop BLE advertising: {e}")
            return False

    def is_advertising(self) -> bool:
        """Check if currently advertising"""
        return self.is_advertising_flag

    def set_credentials_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set callback for received credentials"""
        self.credentials_callback = callback
        if self.logger:
            self.logger.debug("Credentials callback set")

    def _run_ble_server(self):
        """Run BLE server (simulated)"""
        try:
            if self.logger:
                self.logger.info("BLE server started")

            # Simulate receiving credentials after some time (for testing)
            import random
            import time

            while self.is_advertising_flag:
                time.sleep(1)

                # Simulate random credential reception (very low probability for testing)
                if (
                    random.random() < 0.001 and self.credentials_callback
                ):  # 0.1% chance per second
                    # Simulate received credentials
                    ssid = "TestNetwork"
                    password = "testpassword123"

                    if self.logger:
                        self.logger.info(
                            f"Simulated BLE credentials received: SSID={ssid}"
                        )

                    # Call the callback
                    try:
                        self.credentials_callback(ssid, password)
                    except Exception as e:
                        if self.logger:
                            self.logger.error(f"Error in credentials callback: {e}")

            if self.logger:
                self.logger.info("BLE server stopped")

        except Exception as e:
            if self.logger:
                self.logger.error(f"BLE server error: {e}")

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


class MockBluetoothService(IBluetoothService):
    """Mock implementation for testing"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.is_advertising_flag = False
        self.credentials_callback: Optional[Callable[[str, str], None]] = None

    def start_advertising(self, device_info: DeviceInfo) -> bool:
        if self.logger:
            self.logger.info("Mock BLE advertising started")
        self.is_advertising_flag = True
        return True

    def stop_advertising(self) -> bool:
        if self.logger:
            self.logger.info("Mock BLE advertising stopped")
        self.is_advertising_flag = False
        return True

    def is_advertising(self) -> bool:
        return self.is_advertising_flag

    def set_credentials_callback(self, callback: Callable[[str, str], None]) -> None:
        self.credentials_callback = callback
        if self.logger:
            self.logger.debug("Mock credentials callback set")

    def simulate_credentials(self, ssid: str, password: str):
        """Simulate receiving credentials (for testing)"""
        if self.credentials_callback:
            self.credentials_callback(ssid, password)
