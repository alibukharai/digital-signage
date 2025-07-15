"""
Configuration management for the provisioning system
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class BLEConfig:
    """BLE configuration settings"""

    device_name: str = "RockPi3399"
    service_uuid: str = "12345678-1234-1234-1234-123456789abc"
    characteristic_uuid: str = "87654321-4321-4321-4321-cba987654321"
    advertising_interval: int = 100
    connection_timeout: int = 30


@dataclass
class NetworkConfig:
    """Network configuration settings"""

    wifi_scan_timeout: int = 10
    connection_timeout: int = 30
    retry_attempts: int = 3
    enable_ethernet: bool = True
    interface_name: str = "wlan0"
    network_scan_cache_ttl: int = 60  # Cache scan results for 60 seconds


@dataclass
class SecurityConfig:
    """Security configuration settings - Encryption is ALWAYS enabled"""

    # SECURITY: encryption_enabled field REMOVED to prevent security bypass
    # Encryption is now mandatory and cannot be disabled
    session_timeout: int = 900  # 15 minutes
    max_failed_attempts: int = 3
    owner_setup_timeout: int = 300  # 5 minutes
    require_owner_setup: bool = True
    key_rotation_interval: int = 3600  # Rotate keys every hour
    max_key_age: int = 86400  # Maximum key age: 24 hours


@dataclass
class DisplayConfig:
    """Display configuration settings"""

    width: int = 1920
    height: int = 1080
    qr_size: int = 400
    status_font_size: int = 24
    background_color: str = "#000000"
    text_color: str = "#FFFFFF"


@dataclass
class LoggingConfig:
    """Logging configuration settings"""

    level: str = "INFO"
    file_path: str = "logs/rockpi-provisioning.log"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    console_output: bool = True


@dataclass
class SystemConfig:
    """System configuration settings"""

    startup_delay: int = 5
    provisioning_timeout: int = 300  # 5 minutes
    health_check_interval: int = 30
    factory_reset_pin: int = 18
    status_led_pin: int = 16


@dataclass
class ProvisioningConfig:
    """Main configuration class"""

    ble: BLEConfig = field(default_factory=BLEConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    system: SystemConfig = field(default_factory=SystemConfig)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "ble": self.ble.__dict__,
            "network": self.network.__dict__,
            "security": self.security.__dict__,
            "display": self.display.__dict__,
            "logging": self.logging.__dict__,
            "system": self.system.__dict__,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProvisioningConfig":
        """Create from dictionary"""
        return cls(
            ble=BLEConfig(**data.get("ble", {})),
            network=NetworkConfig(**data.get("network", {})),
            security=SecurityConfig(**data.get("security", {})),
            display=DisplayConfig(**data.get("display", {})),
            logging=LoggingConfig(**data.get("logging", {})),
            system=SystemConfig(**data.get("system", {})),
        )


def load_config(config_path: Optional[str] = None) -> ProvisioningConfig:
    """Load configuration from file or create default"""
    if config_path is None:
        # Try multiple locations
        possible_paths = [
            "/etc/rockpi-provisioning/config.json",
            "config/unified_config.json",
            "config.json",
        ]

        for path in possible_paths:
            if os.path.exists(path):
                config_path = path
                break

    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                data = json.load(f)

            # Extract only the fields we understand, ignore unknown ones
            clean_data = {}

            # Handle BLE config
            if "ble" in data:
                ble_data = data["ble"]
                clean_ble = {}
                if "advertising_name" in ble_data:
                    clean_ble["device_name"] = ble_data["advertising_name"]
                if "service_uuid" in ble_data:
                    clean_ble["service_uuid"] = ble_data["service_uuid"]
                if "wifi_credentials_char_uuid" in ble_data:
                    clean_ble["characteristic_uuid"] = ble_data[
                        "wifi_credentials_char_uuid"
                    ]
                if "advertising_timeout" in ble_data:
                    clean_ble["advertising_interval"] = min(
                        ble_data["advertising_timeout"], 1000
                    )
                if "connection_timeout" in ble_data:
                    clean_ble["connection_timeout"] = ble_data["connection_timeout"]
                clean_data["ble"] = clean_ble

            # Handle security config
            if "security" in data:
                sec_data = data["security"]
                clean_sec = {}
                if "require_owner_setup" in sec_data:
                    clean_sec["require_owner_setup"] = sec_data["require_owner_setup"]
                if "owner_setup_timeout" in sec_data:
                    clean_sec["owner_setup_timeout"] = sec_data["owner_setup_timeout"]
                # SECURITY: Remove encryption_enabled bypass - encryption is always mandatory
                # No longer setting encryption_enabled from config to prevent security bypass
                clean_data["security"] = clean_sec

            # Copy known sections directly
            for section in ["network", "display", "logging", "system"]:
                if section in data:
                    clean_data[section] = data[section]

            return ProvisioningConfig.from_dict(clean_data)
        except Exception as e:
            print(f"Warning: Failed to load config from {config_path}: {e}")

    # Return default configuration
    return ProvisioningConfig()


def save_config(config: ProvisioningConfig, config_path: str = "config.json") -> bool:
    """Save configuration to file"""
    try:
        # Ensure directory exists
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            json.dump(config.to_dict(), f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False
