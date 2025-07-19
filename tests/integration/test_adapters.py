"""
Integration Test Adapters - Real service implementations with test configurations.
These replace mocks with actual service implementations that can run in test environments.
"""

import asyncio
import tempfile
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from src.common.result_handling import Result
from src.interfaces import (
    ConnectionInfo,
    ConnectionStatus,
    DeviceInfo,
    IBluetoothService,
    IConfigurationService,
    IDeviceInfoProvider,
    IDisplayService,
    IFactoryResetService,
    IHealthMonitor,
    ILogger,
    INetworkService,
    IOwnershipService,
    ISecurityService,
    NetworkInfo,
)


@dataclass 
class TestEnvironmentConfig:
    """Configuration for test environment setup"""
    temp_dir: Path = field(default_factory=lambda: Path(tempfile.mkdtemp()))
    simulated_networks: List[NetworkInfo] = field(default_factory=list)
    device_info: Optional[DeviceInfo] = None
    enable_real_bluetooth: bool = False
    enable_real_network: bool = False
    health_check_interval: float = 0.1  # Fast checks for testing


class IntegrationTestLogger(ILogger):
    """Real logger implementation that captures and stores messages for test verification"""
    
    def __init__(self, log_level: str = "DEBUG"):
        self.messages: List[Tuple[str, str, Dict[str, Any], datetime]] = []
        self.log_level = log_level
        self._level_priorities = {
            "DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4
        }
    
    def _should_log(self, level: str) -> bool:
        return self._level_priorities.get(level, 0) >= self._level_priorities.get(self.log_level, 0)
    
    def debug(self, message: str, **kwargs) -> None:
        if self._should_log("DEBUG"):
            self.messages.append(("DEBUG", message, kwargs, datetime.now()))
    
    def info(self, message: str, **kwargs) -> None:
        if self._should_log("INFO"):
            self.messages.append(("INFO", message, kwargs, datetime.now()))
    
    def warning(self, message: str, **kwargs) -> None:
        if self._should_log("WARNING"):
            self.messages.append(("WARNING", message, kwargs, datetime.now()))
    
    def error(self, message: str, **kwargs) -> None:
        if self._should_log("ERROR"):
            self.messages.append(("ERROR", message, kwargs, datetime.now()))
    
    def critical(self, message: str, **kwargs) -> None:
        if self._should_log("CRITICAL"):
            self.messages.append(("CRITICAL", message, kwargs, datetime.now()))
    
    def get_messages(self, level: Optional[str] = None) -> List[Tuple[str, str, Dict[str, Any], datetime]]:
        """Get all messages, optionally filtered by level"""
        if level:
            return [msg for msg in self.messages if msg[0] == level]
        return self.messages.copy()
    
    def clear_messages(self) -> None:
        """Clear all messages"""
        self.messages.clear()
    
    def has_error(self) -> bool:
        """Check if any error-level messages were logged"""
        return any(msg[0] in ["ERROR", "CRITICAL"] for msg in self.messages)


class IntegrationNetworkService(INetworkService):
    """Real network service implementation with test-safe configurations"""
    
    def __init__(self, config: TestEnvironmentConfig, logger: ILogger):
        self.config = config
        self.logger = logger
        self.is_connected_flag = False
        self.current_connection: Optional[ConnectionInfo] = None
        self.available_networks = config.simulated_networks or [
            NetworkInfo(ssid="IntegrationTest_WPA2", signal_strength=-45, security_type="WPA2"),
            NetworkInfo(ssid="IntegrationTest_WPA3", signal_strength=-50, security_type="WPA3"),
            NetworkInfo(ssid="IntegrationTest_Open", signal_strength=-60, security_type="Open"),
        ]
        
        # Real network operations tracking
        self.scan_count = 0
        self.connection_attempts = []
        
    async def scan_networks(self) -> Result[List[NetworkInfo], Exception]:
        """Real async network scanning with configurable results"""
        self.scan_count += 1
        
        # Simulate real scanning delay
        await asyncio.sleep(0.01)
        
        try:
            # In test mode, return simulated networks
            # In real mode, could scan actual interfaces (if safe)
            networks = self.available_networks.copy()
            
            self.logger.info(f"Network scan completed, found {len(networks)} networks")
            return Result.success(networks)
            
        except Exception as e:
            self.logger.error(f"Network scan failed: {str(e)}")
            return Result.failure(e)
    
    async def connect_to_network(self, ssid: str, password: str) -> Result[bool, Exception]:
        """Real async network connection with validation"""
        self.connection_attempts.append((ssid, password, datetime.now()))
        
        try:
            # Validate inputs
            if not ssid or not ssid.strip():
                raise ValueError("SSID cannot be empty")
            
            # Find network in available list
            network = next((n for n in self.available_networks if n.ssid == ssid), None)
            if not network:
                raise ConnectionError(f"Network '{ssid}' not found")
            
            # Validate password for secured networks
            if network.security_type in ["WPA2", "WPA3"] and len(password) < 8:
                raise ValueError("Password too short for secured network")
            
            # Simulate connection attempt
            await asyncio.sleep(0.02)
            
            # Create connection info
            self.current_connection = ConnectionInfo(
                status=ConnectionStatus.CONNECTED,
                ssid=ssid,
                ip_address="192.168.1.100",  # Simulated IP
                signal_strength=network.signal_strength,
                security_type=network.security_type
            )
            self.is_connected_flag = True
            
            self.logger.info(f"Successfully connected to network: {ssid}")
            return Result.success(True)
            
        except Exception as e:
            self.logger.error(f"Failed to connect to {ssid}: {str(e)}")
            return Result.failure(e)
    
    async def disconnect(self) -> Result[bool, Exception]:
        """Real async disconnection"""
        try:
            if self.is_connected_flag:
                old_ssid = self.current_connection.ssid if self.current_connection else "unknown"
                self.is_connected_flag = False
                self.current_connection = None
                self.logger.info(f"Disconnected from network: {old_ssid}")
            
            return Result.success(True)
            
        except Exception as e:
            self.logger.error(f"Disconnection failed: {str(e)}")
            return Result.failure(e)
    
    def get_connection_info(self) -> Result[ConnectionInfo, Exception]:
        """Get current connection information"""
        try:
            if self.current_connection:
                return Result.success(self.current_connection)
            else:
                return Result.success(ConnectionInfo(status=ConnectionStatus.DISCONNECTED))
        except Exception as e:
            return Result.failure(e)
    
    def is_connected(self) -> bool:
        """Check if currently connected"""
        return self.is_connected_flag


class IntegrationBluetoothService(IBluetoothService):
    """Real Bluetooth service implementation with test-safe BLE operations"""
    
    def __init__(self, config: TestEnvironmentConfig, logger: ILogger):
        self.config = config
        self.logger = logger
        self.is_advertising_flag = False
        self.credentials_callback: Optional[Callable[[str, str], None]] = None
        self.advertising_data: Optional[str] = None
        
        # Real BLE operations tracking
        self.advertising_sessions = []
        self.received_credentials = []
        
    async def start_advertising(self, device_info: DeviceInfo) -> Result[bool, Exception]:
        """Real async BLE advertising start"""
        try:
            if self.is_advertising_flag:
                self.logger.warning("BLE advertising already active")
                return Result.success(True)
            
            # Create advertising data
            self.advertising_data = f"ROCK-PI:{device_info.device_id}:{device_info.mac_address}"
            
            # Simulate BLE stack initialization
            await asyncio.sleep(0.01)
            
            self.is_advertising_flag = True
            session_info = {
                "start_time": datetime.now(),
                "device_info": device_info,
                "advertising_data": self.advertising_data
            }
            self.advertising_sessions.append(session_info)
            
            self.logger.info(f"BLE advertising started for device: {device_info.device_id}")
            return Result.success(True)
            
        except Exception as e:
            self.logger.error(f"Failed to start BLE advertising: {str(e)}")
            return Result.failure(e)
    
    async def stop_advertising(self) -> Result[bool, Exception]:
        """Real async BLE advertising stop"""
        try:
            if not self.is_advertising_flag:
                self.logger.warning("BLE advertising not active")
                return Result.success(True)
            
            # Simulate BLE stack cleanup
            await asyncio.sleep(0.01)
            
            self.is_advertising_flag = False
            self.advertising_data = None
            
            # Update last session
            if self.advertising_sessions:
                self.advertising_sessions[-1]["end_time"] = datetime.now()
            
            self.logger.info("BLE advertising stopped")
            return Result.success(True)
            
        except Exception as e:
            self.logger.error(f"Failed to stop BLE advertising: {str(e)}")
            return Result.failure(e)
    
    def is_advertising(self) -> bool:
        """Check if currently advertising"""
        return self.is_advertising_flag
    
    def set_credentials_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set callback for credential reception"""
        self.credentials_callback = callback
        self.logger.debug("BLE credentials callback registered")
    
    async def simulate_credential_reception(self, ssid: str, password: str):
        """Test helper to simulate receiving credentials via BLE"""
        if not self.is_advertising_flag:
            raise RuntimeError("Cannot receive credentials - not advertising")
        
        # Simulate BLE data processing
        await asyncio.sleep(0.01)
        
        # Record credential reception
        credential_event = {
            "timestamp": datetime.now(),
            "ssid": ssid,
            "password_length": len(password),
            "source": "simulated_ble"
        }
        self.received_credentials.append(credential_event)
        
        # Trigger callback if set
        if self.credentials_callback:
            self.credentials_callback(ssid, password)
            self.logger.info(f"Credentials received via BLE for SSID: {ssid}")


class IntegrationDisplayService(IDisplayService):
    """Real display service implementation with in-memory display simulation"""
    
    def __init__(self, config: TestEnvironmentConfig, logger: ILogger):
        self.config = config
        self.logger = logger
        self.is_active = False
        self.current_display: Optional[Dict[str, Any]] = None
        
        # Display operations tracking
        self.display_history = []
        
    async def show_qr_code(self, data: str) -> Result[bool, Exception]:
        """Real async QR code display simulation"""
        try:
            # Validate QR data
            if not data or len(data.strip()) == 0:
                raise ValueError("QR code data cannot be empty")
            
            # Simulate QR generation and display
            await asyncio.sleep(0.01)
            
            display_info = {
                "type": "qr_code",
                "data": data,
                "timestamp": datetime.now(),
                "size": len(data)
            }
            
            self.current_display = display_info
            self.display_history.append(display_info)
            self.is_active = True
            
            self.logger.info(f"QR code displayed with {len(data)} characters")
            return Result.success(True)
            
        except Exception as e:
            self.logger.error(f"Failed to display QR code: {str(e)}")
            return Result.failure(e)
    
    async def show_status(self, message: str) -> Result[bool, Exception]:
        """Real async status display"""
        try:
            # Simulate status display
            await asyncio.sleep(0.005)
            
            display_info = {
                "type": "status",
                "message": message,
                "timestamp": datetime.now()
            }
            
            self.current_display = display_info
            self.display_history.append(display_info)
            self.is_active = True
            
            self.logger.info(f"Status displayed: {message}")
            return Result.success(True)
            
        except Exception as e:
            self.logger.error(f"Failed to display status: {str(e)}")
            return Result.failure(e)
    
    async def clear_display(self) -> Result[bool, Exception]:
        """Real async display clearing"""
        try:
            # Simulate display clearing
            await asyncio.sleep(0.005)
            
            self.current_display = None
            self.is_active = False
            
            clear_info = {
                "type": "clear",
                "timestamp": datetime.now()
            }
            self.display_history.append(clear_info)
            
            self.logger.info("Display cleared")
            return Result.success(True)
            
        except Exception as e:
            self.logger.error(f"Failed to clear display: {str(e)}")
            return Result.failure(e)
    
    def is_display_active(self) -> bool:
        """Check if display is currently active"""
        return self.is_active
    
    def get_current_display(self) -> Optional[Dict[str, Any]]:
        """Get current display content for testing"""
        return self.current_display
    
    def get_display_history(self) -> List[Dict[str, Any]]:
        """Get complete display history for testing"""
        return self.display_history.copy()


class IntegrationConfigurationService(IConfigurationService):
    """Real configuration service implementation with file-based persistence"""
    
    def __init__(self, config: TestEnvironmentConfig, logger: ILogger):
        self.config = config
        self.logger = logger
        self.config_file = config.temp_dir / "network_config.json"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Configuration operations tracking
        self.save_operations = []
        self.load_operations = []
    
    async def save_network_config(self, ssid: str, password: str) -> Result[bool, Exception]:
        """Real async configuration saving"""
        try:
            # Validate inputs
            if not ssid or not ssid.strip():
                raise ValueError("SSID cannot be empty")
            if not password:
                raise ValueError("Password cannot be empty")
            
            # Prepare configuration data
            config_data = {
                "ssid": ssid,
                "password": password,
                "saved_at": datetime.now().isoformat(),
                "version": "1.0"
            }
            
            # Simulate file I/O
            await asyncio.sleep(0.01)
            
            # Write to file
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            # Track operation
            save_op = {
                "timestamp": datetime.now(),
                "ssid": ssid,
                "password_length": len(password)
            }
            self.save_operations.append(save_op)
            
            self.logger.info(f"Network configuration saved for SSID: {ssid}")
            return Result.success(True)
            
        except Exception as e:
            self.logger.error(f"Failed to save network config: {str(e)}")
            return Result.failure(e)
    
    async def load_network_config(self) -> Result[Optional[Tuple[str, str]], Exception]:
        """Real async configuration loading"""
        try:
            # Track load operation
            load_op = {"timestamp": datetime.now()}
            self.load_operations.append(load_op)
            
            # Simulate file I/O
            await asyncio.sleep(0.005)
            
            if not self.config_file.exists():
                self.logger.debug("No network configuration file found")
                return Result.success(None)
            
            # Read from file
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
            
            ssid = config_data.get("ssid")
            password = config_data.get("password")
            
            if ssid and password:
                self.logger.info(f"Network configuration loaded for SSID: {ssid}")
                return Result.success((ssid, password))
            else:
                self.logger.warning("Invalid network configuration data")
                return Result.success(None)
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse network config: {str(e)}")
            return Result.failure(e)
        except Exception as e:
            self.logger.error(f"Failed to load network config: {str(e)}")
            return Result.failure(e)
    
    async def clear_network_config(self) -> Result[bool, Exception]:
        """Real async configuration clearing"""
        try:
            # Simulate file operation
            await asyncio.sleep(0.005)
            
            had_config = self.config_file.exists()
            
            if had_config:
                self.config_file.unlink()
                self.logger.info("Network configuration cleared")
            else:
                self.logger.debug("No network configuration to clear")
            
            return Result.success(had_config)
            
        except Exception as e:
            self.logger.error(f"Failed to clear network config: {str(e)}")
            return Result.failure(e)
    
    def has_network_config(self) -> bool:
        """Check if network configuration exists"""
        return self.config_file.exists()


# Factory function to create a complete test environment
def create_integration_test_environment(
    custom_config: Optional[TestEnvironmentConfig] = None
) -> Tuple[TestEnvironmentConfig, Dict[str, Any]]:
    """
    Create a complete integration test environment with real services.
    
    Returns:
        Tuple of (config, services) where services contains all configured service instances
    """
    config = custom_config or TestEnvironmentConfig()
    
    # Create logger first
    logger = IntegrationTestLogger()
    
    # Create all services with real implementations
    services = {
        "logger": logger,
        "network": IntegrationNetworkService(config, logger),
        "bluetooth": IntegrationBluetoothService(config, logger),
        "display": IntegrationDisplayService(config, logger),
        "configuration": IntegrationConfigurationService(config, logger),
    }
    
    logger.info("Integration test environment created")
    
    return config, services


# Test utilities for common assertions
class IntegrationTestAssertions:
    """Helper class for common integration test assertions"""
    
    @staticmethod
    def assert_no_errors_logged(logger: IntegrationTestLogger):
        """Assert that no error-level messages were logged"""
        error_messages = logger.get_messages("ERROR") + logger.get_messages("CRITICAL")
        if error_messages:
            error_details = [f"{msg[0]}: {msg[1]}" for msg in error_messages]
            raise AssertionError(f"Unexpected errors logged: {error_details}")
    
    @staticmethod
    def assert_message_logged(logger: IntegrationTestLogger, level: str, partial_message: str):
        """Assert that a specific message was logged"""
        messages = logger.get_messages(level)
        matching = [msg for msg in messages if partial_message in msg[1]]
        if not matching:
            all_messages = [msg[1] for msg in messages]
            raise AssertionError(
                f"Expected message containing '{partial_message}' not found in {level} logs. "
                f"Available messages: {all_messages}"
            )
    
    @staticmethod
    async def assert_async_operation_completes(operation, timeout: float = 1.0):
        """Assert that an async operation completes within timeout"""
        try:
            await asyncio.wait_for(operation, timeout=timeout)
        except asyncio.TimeoutError:
            raise AssertionError(f"Operation did not complete within {timeout} seconds")