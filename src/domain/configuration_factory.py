"""
Configuration factory for creating appropriate configurations with SOC-aware settings
"""

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from ..common.result_handling import Result
from ..domain.errors import ErrorCode, ErrorSeverity, SystemError
from ..infrastructure.hardware_abstraction import HALFactory
from .configuration import ProvisioningConfig
from .soc_specifications import SOCFamily, SOCSpecification, soc_manager


class IConfigurationLoader(ABC):
    """Abstract configuration loader interface"""

    @abstractmethod
    def can_load(self, path: str) -> bool:
        """Check if this loader can handle the given path"""
        pass

    @abstractmethod
    def load(self, path: str) -> Dict[str, Any]:
        """Load configuration from path"""
        pass


class JsonConfigurationLoader(IConfigurationLoader):
    """JSON configuration loader"""

    def can_load(self, path: str) -> bool:
        return path.endswith(".json")

    def load(self, path: str) -> Dict[str, Any]:
        with open(path, "r") as f:
            return json.load(f)


class YamlConfigurationLoader(IConfigurationLoader):
    """YAML configuration loader (example extension)"""

    def can_load(self, path: str) -> bool:
        return path.endswith((".yaml", ".yml"))

    def load(self, path: str) -> Dict[str, Any]:
        try:
            import yaml

            with open(path, "r") as f:
                return yaml.safe_load(f)
        except ImportError:
            raise ImportError("PyYAML required for YAML configuration")


class ConfigurationLoaderRegistry:
    """Registry for configuration loaders"""

    def __init__(self):
        self._loaders = []

    def register_loader(self, loader: IConfigurationLoader):
        """Register a new configuration loader"""
        self._loaders.append(loader)

    def get_loader(self, path: str) -> Optional[IConfigurationLoader]:
        """Get appropriate loader for path"""
        for loader in self._loaders:
            if loader.can_load(path):
                return loader
        return None


class ConfigurationFactory:
    """Factory for creating configurations with SOC awareness and extensible loading"""

    def __init__(self):
        self.registry = ConfigurationLoaderRegistry()
        # Register default loaders
        self.registry.register_loader(JsonConfigurationLoader())
        # self.registry.register_loader(YamlConfigurationLoader())  # Optional

    def load_config(self, config_path: Optional[str] = None) -> ProvisioningConfig:
        """Load configuration using appropriate loader with SOC optimization"""
        if config_path is None:
            config_path = self._find_config_file()

        if config_path and Path(config_path).exists():
            loader = self.registry.get_loader(config_path)
            if loader:
                try:
                    data = loader.load(config_path)
                    return self._create_config_from_data(data)
                except Exception as e:
                    # Log error and fall back to SOC-optimized default
                    import logging
            logging.getLogger(__name__).warning(f"Failed to load config from {config_path}: {e}")

        return self.create_default()  # SOC-optimized default configuration

    def create_from_file(self, file_path: str) -> Result[ProvisioningConfig, Exception]:
        """Create configuration from JSON file with SOC optimization"""
        try:
            path = Path(file_path)
            if not path.exists():
                return Result.failure(
                    SystemError(
                        ErrorCode.CONFIG_FILE_NOT_FOUND,
                        f"Configuration file not found: {file_path}",
                        ErrorSeverity.HIGH,
                    )
                )

            loader = self.registry.get_loader(file_path)
            if not loader:
                return Result.failure(
                    SystemError(
                        ErrorCode.CONFIG_INVALID_FORMAT,
                        f"No loader available for file type: {file_path}",
                        ErrorSeverity.HIGH,
                    )
                )

            config_data = loader.load(file_path)
            config = self._create_config_from_data(config_data)
            return Result.success(config)

        except json.JSONDecodeError as e:
            return Result.failure(
                SystemError(
                    ErrorCode.CONFIG_INVALID_FORMAT,
                    f"Invalid JSON in config file: {e}",
                    ErrorSeverity.HIGH,
                )
            )
        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.CONFIG_LOAD_FAILED,
                    f"Failed to load configuration: {e}",
                    ErrorSeverity.HIGH,
                )
            )

    def create_from_dict(
        self, config_dict: Dict
    ) -> Result[ProvisioningConfig, Exception]:
        """Create configuration from dictionary with SOC optimization"""
        try:
            config = self._create_config_from_data(config_dict)
            return Result.success(config)
        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.CONFIG_INVALID_FORMAT,
                    f"Failed to build configuration from dict: {e}",
                    ErrorSeverity.HIGH,
                )
            )

    def create_default(self) -> ProvisioningConfig:
        """Create default configuration optimized for detected SOC"""
        # Detect current SOC
        soc_spec = soc_manager.detect_soc()

        # Create base configuration
        config = ProvisioningConfig()

        # Apply SOC-specific optimizations
        if soc_spec:
            config = self._apply_soc_optimizations(config, soc_spec)

        return config

    def create_for_soc(self, soc_name: str) -> Result[ProvisioningConfig, Exception]:
        """Create configuration optimized for specific SOC"""
        try:
            soc_spec = soc_manager.get_soc_by_name(soc_name)
            if not soc_spec:
                return Result.failure(
                    SystemError(
                        ErrorCode.CONFIG_INVALID_FORMAT,
                        f"Unsupported SOC: {soc_name}",
                        ErrorSeverity.HIGH,
                    )
                )

            config = ProvisioningConfig()
            config = self._apply_soc_optimizations(config, soc_spec)
            return Result.success(config)

        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.CONFIG_LOAD_FAILED,
                    f"Failed to create SOC-specific configuration: {e}",
                    ErrorSeverity.HIGH,
                )
            )

    def create_from_environment(self) -> Result[ProvisioningConfig, Exception]:
        """Create configuration from environment variables with SOC detection"""
        try:
            config = self.create_default()  # SOC-optimized default

            # Override with environment variables if present
            if os.getenv("BLE_DEVICE_NAME"):
                config.ble.device_name = os.getenv("BLE_DEVICE_NAME")

            if os.getenv("WIFI_INTERFACE"):
                config.network.interface_name = os.getenv("WIFI_INTERFACE")

            if os.getenv("LOG_LEVEL"):
                config.logging.level = os.getenv("LOG_LEVEL")

            # SOC-specific environment overrides
            if os.getenv("SOC_NAME"):
                soc_spec = soc_manager.get_soc_by_name(os.getenv("SOC_NAME"))
                if soc_spec:
                    config = self._apply_soc_optimizations(config, soc_spec)

            return Result.success(config)

        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.CONFIG_LOAD_FAILED,
                    f"Failed to load configuration from environment: {e}",
                    ErrorSeverity.MEDIUM,
                )
            )

    def _find_config_file(self) -> Optional[str]:
        """Find configuration file in standard locations"""
        possible_paths = [
            "/etc/rockpi-provisioning/config.json",
            "config/unified_config.json",
            "config.json",
            "/etc/rockpi-provisioning/config.yaml",  # Support for future YAML
            "config/unified_config.yaml",
            "config.yaml",
        ]

        for path in possible_paths:
            if Path(path).exists():
                return path
        return None

    def _create_config_from_data(self, data: Dict[str, Any]) -> ProvisioningConfig:
        """Create ProvisioningConfig from loaded data with SOC awareness"""
        config = self._build_config_from_dict(data)

        # Apply SOC optimizations if not explicitly overridden
        if "hardware" not in data or "soc" not in data.get("hardware", {}):
            soc_spec = soc_manager.detect_soc()
            if soc_spec:
                config = self._apply_soc_optimizations(config, soc_spec)
        else:
            # Use specified SOC from config
            soc_name = data["hardware"]["soc"]
            soc_spec = soc_manager.get_soc_by_name(soc_name)
            if soc_spec:
                config = self._apply_soc_optimizations(config, soc_spec)

        return config

    def _apply_soc_optimizations(
        self, config: ProvisioningConfig, soc_spec: SOCSpecification
    ) -> ProvisioningConfig:
        """Apply SOC-specific optimizations to configuration"""

        # Create HAL for hardware-specific optimizations
        hal = HALFactory.create_hal(soc_spec)
        hal.initialize()

        # Update device name based on SOC
        if soc_spec.name == "OP1":
            config.ble.device_name = "RockPi4B-Plus"
        elif soc_spec.name == "RK3399":
            config.ble.device_name = "RockPi4"
        elif soc_spec.family == SOCFamily.BROADCOM:
            if soc_spec.name == "BCM2712":
                config.ble.device_name = "RaspberryPi5"
            elif soc_spec.name == "BCM2711":
                config.ble.device_name = "RaspberryPi4"
            else:
                config.ble.device_name = "RaspberryPi"
        elif soc_spec.family == SOCFamily.ALLWINNER:
            if soc_spec.name in ["H618", "H616"]:
                config.ble.device_name = f"OrangePi-{soc_spec.name}"
            else:
                config.ble.device_name = "OrangePi"
        elif soc_spec.family == SOCFamily.MEDIATEK:
            config.ble.device_name = f"MediaTek-{soc_spec.name}"
        elif soc_spec.family == SOCFamily.QUALCOMM:
            config.ble.device_name = f"Qualcomm-{soc_spec.name}"
        else:
            config.ble.device_name = f"DigitalSignage-{soc_spec.name}"

        # Optimize BLE settings based on Bluetooth version
        if soc_spec.connectivity.bluetooth_version.startswith("5"):
            config.ble.advertising_interval = 50  # Faster advertising for BT 5.0+
            config.ble.connection_timeout = 15  # Shorter timeout for better performance
        elif soc_spec.connectivity.bluetooth_version.startswith("4"):
            config.ble.advertising_interval = 100
            config.ble.connection_timeout = 30

        # Optimize network settings based on capabilities
        if "802.11ac" in soc_spec.connectivity.wifi_standards:
            config.network.wifi_scan_timeout = 5  # Faster scanning
        if "802.11ax" in soc_spec.connectivity.wifi_standards:
            config.network.wifi_scan_timeout = 3  # Even faster for WiFi 6

        # Optimize display settings based on capabilities
        display_info = hal.get_display_info()
        if "4K" in display_info.get("max_resolution", ""):
            config.display.width = 3840
            config.display.height = 2160
            config.display.qr_size = 800  # Larger QR for 4K displays
        elif "1080p" in display_info.get("max_resolution", ""):
            config.display.width = 1920
            config.display.height = 1080
            config.display.qr_size = 400

        # Set GPIO pins based on HAL mapping
        gpio_mapping = hal.get_gpio_mapping()
        if "reset_button" in gpio_mapping:
            config.system.factory_reset_pin = gpio_mapping["reset_button"]
        if "status_led_green" in gpio_mapping:
            config.system.status_led_pin = gpio_mapping["status_led_green"]

        # Performance optimizations based on SOC capabilities
        if soc_spec.performance.cpu_cores >= 6:
            config.system.health_check_interval = 15  # More frequent health checks
        elif soc_spec.performance.cpu_cores >= 4:
            config.system.health_check_interval = 30
        else:
            config.system.health_check_interval = 60  # Less frequent for lower-end SOCs

        # Memory-based optimizations
        if soc_spec.performance.memory_max_gb >= 4:
            config.logging.max_file_size = (
                20 * 1024 * 1024
            )  # 20MB for high-memory systems
            config.logging.backup_count = 10
        elif soc_spec.performance.memory_max_gb >= 2:
            config.logging.max_file_size = 10 * 1024 * 1024  # 10MB
            config.logging.backup_count = 5
        else:
            config.logging.max_file_size = 5 * 1024 * 1024  # 5MB for low-memory systems
            config.logging.backup_count = 3

        # Power management optimizations
        if soc_spec.power.poe_support:
            config.system.provisioning_timeout = 600  # Longer timeout for PoE systems

        # Network interface optimization using HAL
        network_interfaces = hal.get_network_interfaces()
        if "wlan0" in network_interfaces:
            config.network.interface_name = "wlan0"
        elif network_interfaces:
            config.network.interface_name = network_interfaces[0]
        else:
            config.network.interface_name = "wlan0"  # Safe default

        return config

    def _build_config_from_dict(self, config_dict: Dict) -> ProvisioningConfig:
        """Build configuration object from dictionary with SOC awareness"""
        from .configuration import (
            BLEConfig,
            DisplayConfig,
            LoggingConfig,
            NetworkConfig,
            SecurityConfig,
            SystemConfig,
        )

        # Build individual config sections
        ble_config = BLEConfig()
        if "ble" in config_dict:
            ble_data = config_dict["ble"]
            for key, value in ble_data.items():
                if hasattr(ble_config, key):
                    setattr(ble_config, key, value)

        network_config = NetworkConfig()
        if "network" in config_dict:
            network_data = config_dict["network"]
            for key, value in network_data.items():
                if hasattr(network_config, key):
                    setattr(network_config, key, value)

        security_config = SecurityConfig()
        if "security" in config_dict:
            security_data = config_dict["security"]
            for key, value in security_data.items():
                if hasattr(security_config, key):
                    setattr(security_config, key, value)

        display_config = DisplayConfig()
        if "display" in config_dict:
            display_data = config_dict["display"]
            for key, value in display_data.items():
                if hasattr(display_config, key):
                    setattr(display_config, key, value)

        logging_config = LoggingConfig()
        if "logging" in config_dict:
            logging_data = config_dict["logging"]
            for key, value in logging_data.items():
                if hasattr(logging_config, key):
                    setattr(logging_config, key, value)

        system_config = SystemConfig()
        if "system" in config_dict:
            system_data = config_dict["system"]
            for key, value in system_data.items():
                if hasattr(system_config, key):
                    setattr(system_config, key, value)

        return ProvisioningConfig(
            ble=ble_config,
            network=network_config,
            security=security_config,
            display=display_config,
            logging=logging_config,
            system=system_config,
        )
