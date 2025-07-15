"""
Improved configuration service that properly follows LSP and uses Result pattern for consistent error handling
"""

import hashlib
import json
import os
import shutil
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import jsonschema
    from jsonschema import ValidationError as JsonSchemaValidationError
    from jsonschema import validate

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

from ..common.result_handling import Result
from ..domain.errors import ConfigurationError, ErrorCode, ErrorSeverity
from ..interfaces import IConfigurationService, ILogger

# JSON Schema for network configuration validation
NETWORK_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "ssid": {
            "type": "string",
            "minLength": 1,
            "maxLength": 32,
            "pattern": "^[\\x20-\\x7E]+$",  # Printable ASCII characters only
        },
        "password": {"type": "string", "minLength": 8, "maxLength": 64},
        "security_type": {"type": "string", "enum": ["WPA2", "WPA3", "WEP", "OPEN"]},
        "enterprise": {
            "type": "object",
            "properties": {
                "identity": {"type": "string"},
                "ca_cert": {"type": "string"},
                "client_cert": {"type": "string"},
                "private_key": {"type": "string"},
            },
            "required": [],
        },
        "created_at": {"type": "string"},
        "version": {"type": "integer", "minimum": 1},
    },
    "required": ["ssid", "password"],
    "additionalProperties": False,
}

# Configuration file permissions (read/write for owner only)
SECURE_FILE_PERMISSIONS = 0o600


class BaseConfigurationService(IConfigurationService):
    """Base implementation ensuring consistent behavior"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self._ensure_config_directory()

    def _ensure_config_directory(self) -> None:
        """Ensure configuration directory exists"""
        # Template method pattern - subclasses can override
        pass

    def _log_info(self, message: str) -> None:
        """Consistent logging helper"""
        if self.logger:
            self.logger.info(message)

    def _log_error(self, message: str) -> None:
        """Consistent logging helper"""
        if self.logger:
            self.logger.error(message)

    def _log_warning(self, message: str) -> None:
        """Consistent logging helper"""
        if self.logger:
            self.logger.warning(message)


class LocalConfigurationService(BaseConfigurationService):
    """Local file-based configuration service"""

    def __init__(
        self, logger: Optional[ILogger] = None, base_path: Optional[str] = None
    ):
        self.base_path = Path(base_path) if base_path else Path("config")
        super().__init__(logger)
        self.network_config_file = "network.json"

    def _ensure_config_directory(self) -> None:
        """Ensure configuration directory exists"""
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            self._log_info(f"Configuration directory ensured: {self.base_path}")
        except PermissionError as e:
            # Try user config directory as fallback
            user_config = Path.home() / ".config" / "rockpi-provisioning"
            user_config.mkdir(parents=True, exist_ok=True)
            self.base_path = user_config
            self._log_warning(
                f"Using user config directory due to permissions: {self.base_path}"
            )
        except Exception as e:
            self._log_error(f"Failed to create config directory: {e}")
            raise ConfigurationError(
                ErrorCode.CONFIG_WRITE_FAILED,
                f"Cannot create configuration directory: {e}",
                ErrorSeverity.HIGH,
            )

    def save_network_config(
        self,
        ssid: str,
        password: str,
        security_type: str = "WPA2",
        enterprise: Optional[Dict[str, str]] = None,
    ) -> Result[bool, Exception]:
        """Save network configuration with consistent error handling"""
        if not ssid or not password:
            error_msg = "Invalid network configuration: SSID and password required"
            self._log_error(error_msg)
            return Result.failure(
                ConfigurationError(
                    ErrorCode.CONFIG_WRITE_FAILED,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

        # Validate using JSON Schema
        if JSONSCHEMA_AVAILABLE:
            config_data = {
                "ssid": ssid,
                "password": password,
                "security_type": security_type,
                "enterprise": enterprise or {},
                "created_at": datetime.utcnow().isoformat(),
                "version": 1,
            }

            try:
                validate(instance=config_data, schema=NETWORK_CONFIG_SCHEMA)
            except JsonSchemaValidationError as e:
                error_msg = f"Network configuration validation error: {e.message}"
                self._log_error(error_msg)
                return Result.failure(
                    ConfigurationError(
                        ErrorCode.CONFIG_WRITE_FAILED,
                        error_msg,
                        ErrorSeverity.MEDIUM,
                    )
                )
        else:
            # Fallback for systems without jsonschema
            self._log_warning(
                "JSON Schema validation not available - skipping validation"
            )
            config_data = {
                "ssid": ssid,
                "password": password,
                "security_type": security_type,
                "enterprise": enterprise or {},
                "created_at": datetime.utcnow().isoformat(),
                "version": 1,
            }

        try:
            config_path = self.base_path / self.network_config_file

            # Atomic write operation
            temp_path = config_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                import json

                json.dump(config_data, f, indent=2)

            # Move to final location
            temp_path.replace(config_path)

            # Set secure permissions
            try:
                import os

                os.chmod(config_path, SECURE_FILE_PERMISSIONS)
            except OSError as e:
                self._log_warning(f"Could not set secure permissions: {e}")

            self._log_info(f"Network config saved to {config_path}")
            return Result.success(True)

        except Exception as e:
            error_msg = f"Failed to save network config: {e}"
            self._log_error(error_msg)
            return Result.failure(
                ConfigurationError(
                    ErrorCode.CONFIG_WRITE_FAILED,
                    error_msg,
                    ErrorSeverity.HIGH,
                )
            )

    def load_network_config(self) -> Result[Optional[Tuple[str, str]], Exception]:
        """Load network configuration with consistent error handling"""
        config_paths = [
            self.base_path / self.network_config_file,
            Path.home() / ".config" / "rockpi-provisioning" / self.network_config_file,
        ]

        for config_path in config_paths:
            if not config_path.exists():
                continue

            try:
                with open(config_path, "r") as f:
                    config_data = json.load(f)

                ssid = config_data.get("ssid")
                password = config_data.get("password")

                if ssid and password:
                    self._log_info(f"Network config loaded from {config_path}")
                    return Result.success((ssid, password))
                else:
                    self._log_warning(f"Invalid network config in {config_path}")

            except (json.JSONDecodeError, PermissionError, KeyError) as e:
                self._log_error(f"Failed to load config from {config_path}: {e}")
                continue

        self._log_info("No valid network configuration found")
        return Result.success(None)

    def clear_network_config(self) -> Result[bool, Exception]:
        """Clear network configuration with consistent error handling"""
        config_paths = [
            self.base_path / self.network_config_file,
            Path.home() / ".config" / "rockpi-provisioning" / self.network_config_file,
        ]

        cleared_any = False
        errors = []

        for config_path in config_paths:
            if config_path.exists():
                try:
                    config_path.unlink()
                    self._log_info(f"Cleared network config: {config_path}")
                    cleared_any = True
                except Exception as e:
                    error_msg = f"Failed to clear config {config_path}: {e}"
                    self._log_error(error_msg)
                    errors.append(error_msg)

        if errors and not cleared_any:
            # All operations failed
            return Result.failure(
                ConfigurationError(
                    ErrorCode.CONFIG_WRITE_FAILED,
                    f"Failed to clear network config: {'; '.join(errors)}",
                    ErrorSeverity.MEDIUM,
                )
            )

        return Result.success(cleared_any)

    def has_network_config(self) -> bool:
        """Check if network configuration exists"""
        config_paths = [
            self.base_path / self.network_config_file,
            Path.home() / ".config" / "rockpi-provisioning" / self.network_config_file,
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, "r") as f:
                        config_data = json.load(f)

                    if config_data.get("ssid") and config_data.get("password"):
                        return True

                except (json.JSONDecodeError, PermissionError, KeyError):
                    continue

        return False


class RemoteConfigurationService(BaseConfigurationService):
    """Remote configuration service (example of LSP compliance)"""

    def __init__(self, api_endpoint: str, logger: Optional[ILogger] = None):
        self.api_endpoint = api_endpoint
        super().__init__(logger)

    def save_network_config(self, ssid: str, password: str) -> Result[bool, Exception]:
        """Save to remote service - same interface, different implementation"""
        if not ssid or not password:
            error_msg = "Invalid network configuration: SSID and password required"
            self._log_error(error_msg)
            return Result.failure(
                ConfigurationError(
                    ErrorCode.CONFIG_WRITE_FAILED,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

        try:
            # Simulate remote API call
            # In real implementation, this would make HTTP request
            self._log_info(f"Would save network config to {self.api_endpoint}")
            return Result.success(True)
        except Exception as e:
            error_msg = f"Failed to save to remote service: {e}"
            self._log_error(error_msg)
            return Result.failure(
                ConfigurationError(
                    ErrorCode.CONFIG_WRITE_FAILED,
                    error_msg,
                    ErrorSeverity.HIGH,
                )
            )

    def load_network_config(self) -> Result[Optional[Tuple[str, str]], Exception]:
        """Load from remote service"""
        try:
            # Simulate remote API call
            self._log_info(f"Would load network config from {self.api_endpoint}")
            return Result.success(None)  # No config available
        except Exception as e:
            error_msg = f"Failed to load from remote service: {e}"
            self._log_error(error_msg)
            return Result.failure(
                ConfigurationError(
                    ErrorCode.CONFIG_READ_FAILED,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

    def clear_network_config(self) -> Result[bool, Exception]:
        """Clear from remote service"""
        try:
            self._log_info(f"Would clear network config from {self.api_endpoint}")
            return Result.success(True)
        except Exception as e:
            error_msg = f"Failed to clear from remote service: {e}"
            self._log_error(error_msg)
            return Result.failure(
                ConfigurationError(
                    ErrorCode.CONFIG_WRITE_FAILED,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

    def has_network_config(self) -> bool:
        """Check if remote service has network configuration"""
        try:
            # Simulate remote API call
            self._log_info(f"Would check network config from {self.api_endpoint}")
            return False  # No config available in this simulation
        except Exception as e:
            self._log_error(f"Failed to check remote service: {e}")
            return False
