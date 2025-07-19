"""
Test hardware adapters for integration testing without mocks
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any
from unittest.mock import patch
import tempfile
import os

from ...common.result_handling import Result
from ...domain.errors import ErrorCode, ErrorSeverity, SystemError
from ...interfaces import ILogger


class TestHardwareAdapter:
    """Test adapter for hardware operations that simulates real hardware"""
    
    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self._test_data_dir = tempfile.mkdtemp(prefix="test_hardware_")
        self._setup_test_environment()

    def _setup_test_environment(self):
        """Setup test environment with simulated hardware files"""
        # Create test machine-id
        os.makedirs(f"{self._test_data_dir}/etc", exist_ok=True)
        with open(f"{self._test_data_dir}/etc/machine-id", "w") as f:
            f.write("a1b2c3d4e5f6789012345678901234567890abcd")
        
        # Create test network interfaces
        os.makedirs(f"{self._test_data_dir}/sys/class/net/wlan0", exist_ok=True)
        with open(f"{self._test_data_dir}/sys/class/net/wlan0/address", "w") as f:
            f.write("aa:bb:cc:dd:ee:ff")
        
        os.makedirs(f"{self._test_data_dir}/sys/class/net/eth0", exist_ok=True)
        with open(f"{self._test_data_dir}/sys/class/net/eth0/address", "w") as f:
            f.write("11:22:33:44:55:66")
        
        # Create test device tree info
        os.makedirs(f"{self._test_data_dir}/proc/device-tree", exist_ok=True)
        with open(f"{self._test_data_dir}/proc/device-tree/compatible", "w") as f:
            f.write("rockchip,rk3399-op1\x00rockchip,rk3399\x00")
        
        with open(f"{self._test_data_dir}/proc/device-tree/model", "w") as f:
            f.write("ROCK Pi 4B Plus\x00")
        
        # Create test DMI info
        os.makedirs(f"{self._test_data_dir}/sys/class/dmi/id", exist_ok=True)
        with open(f"{self._test_data_dir}/sys/class/dmi/id/board_name", "w") as f:
            f.write("ROCK Pi 4B+")
        
        with open(f"{self._test_data_dir}/sys/class/dmi/id/bios_version", "w") as f:
            f.write("2023.04")

    def patch_file_system(self):
        """Context manager to patch file system calls to use test data"""
        def patched_open(file, mode='r', **kwargs):
            # Redirect certain paths to test data
            if file.startswith('/etc/machine-id'):
                file = f"{self._test_data_dir}/etc/machine-id"
            elif file.startswith('/sys/class/net/'):
                file = file.replace('/sys/class/net', f"{self._test_data_dir}/sys/class/net")
            elif file.startswith('/proc/device-tree/'):
                file = file.replace('/proc/device-tree', f"{self._test_data_dir}/proc/device-tree")
            elif file.startswith('/sys/class/dmi/id/'):
                file = file.replace('/sys/class/dmi/id', f"{self._test_data_dir}/sys/class/dmi/id")
            return open(file, mode, **kwargs)

        return patch('builtins.open', side_effect=patched_open)

    def cleanup(self):
        """Clean up test environment"""
        import shutil
        if os.path.exists(self._test_data_dir):
            shutil.rmtree(self._test_data_dir)


class TestNetworkAdapter:
    """Test adapter for network operations"""
    
    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self._networks = [
            {
                "ssid": "TestNetwork1", 
                "signal": -45, 
                "security": "WPA2",
                "frequency": 2437
            },
            {
                "ssid": "TestNetwork2", 
                "signal": -65, 
                "security": "WPA3",
                "frequency": 5180
            },
            {
                "ssid": "OpenNetwork", 
                "signal": -50, 
                "security": "Open",
                "frequency": 2462
            }
        ]
        self._connected_network: Optional[str] = None
        self._connection_success_rate = 0.9  # 90% success rate for testing

    async def scan_networks(self) -> Result[List[Dict[str, Any]], Exception]:
        """Simulate network scanning"""
        try:
            # Add some delay to simulate real scanning
            await asyncio.sleep(0.1)
            
            if self.logger:
                self.logger.info(f"Test network scan found {len(self._networks)} networks")
            
            return Result.success(self._networks.copy())
            
        except Exception as e:
            return Result.failure(e)

    async def connect_to_network(self, ssid: str, password: str) -> Result[bool, Exception]:
        """Simulate network connection"""
        try:
            # Find the network
            network = next((n for n in self._networks if n["ssid"] == ssid), None)
            if not network:
                return Result.failure(
                    SystemError(
                        message=f"Network {ssid} not found",
                        error_code=ErrorCode.NETWORK_ERROR,
                        severity=ErrorSeverity.MEDIUM,
                    )
                )
            
            # Simulate connection delay
            await asyncio.sleep(0.2)
            
            # Simulate occasional failures
            import random
            if random.random() < self._connection_success_rate:
                self._connected_network = ssid
                if self.logger:
                    self.logger.info(f"Test connection to {ssid} successful")
                return Result.success(True)
            else:
                return Result.failure(
                    SystemError(
                        message=f"Connection to {ssid} failed (simulated)",
                        error_code=ErrorCode.NETWORK_ERROR,
                        severity=ErrorSeverity.MEDIUM,
                    )
                )
                
        except Exception as e:
            return Result.failure(e)

    def get_connected_network(self) -> Optional[str]:
        """Get currently connected network"""
        return self._connected_network

    def set_networks(self, networks: List[Dict[str, Any]]):
        """Set available networks for testing"""
        self._networks = networks

    def set_connection_success_rate(self, rate: float):
        """Set connection success rate for testing failures"""
        self._connection_success_rate = max(0.0, min(1.0, rate))


class TestBLEAdapter:
    """Test adapter for Bluetooth Low Energy operations"""
    
    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self._is_advertising = False
        self._connected_devices: List[str] = []
        self._received_credentials: List[Dict[str, Any]] = []

    async def start_advertising(self) -> Result[bool, Exception]:
        """Simulate BLE advertising"""
        try:
            await asyncio.sleep(0.05)  # Simulate startup delay
            self._is_advertising = True
            if self.logger:
                self.logger.info("Test BLE advertising started")
            return Result.success(True)
        except Exception as e:
            return Result.failure(e)

    async def stop_advertising(self) -> Result[bool, Exception]:
        """Simulate stopping BLE advertising"""
        try:
            self._is_advertising = False
            if self.logger:
                self.logger.info("Test BLE advertising stopped")
            return Result.success(True)
        except Exception as e:
            return Result.failure(e)

    def is_advertising(self) -> bool:
        """Check if currently advertising"""
        return self._is_advertising

    async def receive_credentials(self) -> Result[Optional[Dict[str, Any]], Exception]:
        """Simulate receiving credentials via BLE"""
        try:
            # Return pending credentials if any
            if self._received_credentials:
                credentials = self._received_credentials.pop(0)
                if self.logger:
                    self.logger.info(f"Test BLE received credentials for SSID: {credentials.get('ssid')}")
                return Result.success(credentials)
            
            return Result.success(None)
            
        except Exception as e:
            return Result.failure(e)

    def simulate_credential_reception(self, ssid: str, password: str, security_type: str = "WPA2"):
        """Simulate receiving credentials for testing"""
        credentials = {
            "ssid": ssid,
            "password": password,
            "security_type": security_type,
            "timestamp": time.time()
        }
        self._received_credentials.append(credentials)

    def get_connected_devices(self) -> List[str]:
        """Get list of connected device IDs"""
        return self._connected_devices.copy()


class TestDisplayAdapter:
    """Test adapter for display operations"""
    
    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self._displayed_content: Optional[Dict[str, Any]] = None
        self._display_active = False

    def display_qr_code(self, data: str) -> Result[bool, Exception]:
        """Simulate QR code display"""
        try:
            self._displayed_content = {
                "type": "qr_code",
                "data": data,
                "timestamp": time.time()
            }
            self._display_active = True
            
            if self.logger:
                self.logger.info(f"Test display showing QR code with {len(data)} chars")
            
            return Result.success(True)
            
        except Exception as e:
            return Result.failure(e)

    def hide_display(self) -> Result[bool, Exception]:
        """Simulate hiding display"""
        try:
            self._display_active = False
            if self.logger:
                self.logger.info("Test display hidden")
            return Result.success(True)
        except Exception as e:
            return Result.failure(e)

    def is_display_active(self) -> bool:
        """Check if display is currently active"""
        return self._display_active

    def get_displayed_content(self) -> Optional[Dict[str, Any]]:
        """Get currently displayed content for testing"""
        return self._displayed_content


class TestConfigurationAdapter:
    """Test adapter for configuration operations"""
    
    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self._config_data: Dict[str, Any] = {
            "network": {
                "interface": "wlan0",
                "scan_timeout": 10,
                "connection_timeout": 30
            },
            "display": {
                "width": 1920,
                "height": 1080,
                "background_color": "white"
            },
            "bluetooth": {
                "device_name": "TestDevice",
                "advertising_interval": 100
            }
        }

    def get_config(self, section: str) -> Result[Dict[str, Any], Exception]:
        """Get configuration section"""
        try:
            if section in self._config_data:
                return Result.success(self._config_data[section].copy())
            else:
                return Result.failure(
                    SystemError(
                        message=f"Configuration section {section} not found",
                        error_code=ErrorCode.CONFIG_ERROR,
                        severity=ErrorSeverity.MEDIUM,
                    )
                )
        except Exception as e:
            return Result.failure(e)

    def set_config(self, section: str, data: Dict[str, Any]) -> Result[bool, Exception]:
        """Set configuration section"""
        try:
            self._config_data[section] = data.copy()
            if self.logger:
                self.logger.info(f"Test config updated section: {section}")
            return Result.success(True)
        except Exception as e:
            return Result.failure(e)

    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration data for testing"""
        return self._config_data.copy()


class TestServiceFactory:
    """Factory for creating test service instances with test adapters"""
    
    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.hardware_adapter = TestHardwareAdapter(logger)
        self.network_adapter = TestNetworkAdapter(logger)
        self.ble_adapter = TestBLEAdapter(logger)
        self.display_adapter = TestDisplayAdapter(logger)
        self.config_adapter = TestConfigurationAdapter(logger)

    def create_device_info_provider(self):
        """Create device info provider with test adapter"""
        from ..device.info_provider import DeviceInfoProvider
        
        # Use the hardware adapter to provide test data
        provider = DeviceInfoProvider(self.logger)
        
        # Patch the file system operations to use test data
        return provider

    def create_network_service(self):
        """Create network service with test adapter"""
        # This would be implemented based on your actual network service
        # For now, return the test adapter directly
        return self.network_adapter

    def create_bluetooth_service(self):
        """Create Bluetooth service with test adapter"""
        return self.ble_adapter

    def create_display_service(self):
        """Create display service with test adapter"""
        return self.display_adapter

    def cleanup(self):
        """Clean up all test adapters"""
        self.hardware_adapter.cleanup()