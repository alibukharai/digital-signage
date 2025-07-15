"""
Configuration service implementation
"""

import json
import os
from pathlib import Path
from typing import Optional, Tuple

from ..domain.errors import ErrorCode, ErrorSeverity, SystemError
from ..interfaces import IConfigurationService, ILogger


class ConfigurationService(IConfigurationService):
    """Concrete implementation of configuration service"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        # Use more accessible paths for development/testing
        self.config_dir = Path("config")
        self.user_config_dir = Path.home() / ".config" / "rockpi-provisioning"
        self.network_config_file = "network.json"

        # Ensure directories exist - try user config first
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            self.config_base_dir = self.config_dir
        except PermissionError:
            # Fallback to user config directory
            self.user_config_dir.mkdir(parents=True, exist_ok=True)
            self.config_base_dir = self.user_config_dir
            if self.logger:
                self.logger.warning(
                    f"Using user config directory: {self.user_config_dir}"
                )

        if self.logger:
            self.logger.info(
                f"Configuration service initialized with base dir: {self.config_base_dir}"
            )

    def save_network_config(self, ssid: str, password: str) -> bool:
        """Save network configuration"""
        try:
            config_data = {
                "ssid": ssid,
                "password": password,
                "saved_at": str(Path(__file__).stat().st_mtime),  # timestamp
            }

            # Save to the accessible base directory
            config_path = self.config_base_dir / self.network_config_file

            with open(config_path, "w") as f:
                json.dump(config_data, f, indent=2)

            # Make file readable only by owner for security
            try:
                os.chmod(config_path, 0o600)
            except OSError:
                pass  # Ignore if we can't set permissions

            if self.logger:
                self.logger.info(f"Network config saved to {config_path}")

            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save network config: {e}")
            return False

    def load_network_config(self) -> Optional[Tuple[str, str]]:
        """Load saved network configuration"""
        try:
            # Check the base directory and fallback locations
            config_paths = [
                self.config_base_dir / self.network_config_file,
                self.user_config_dir / self.network_config_file,
                Path("config") / self.network_config_file,  # fallback
            ]

            for config_path in config_paths:
                if config_path.exists():
                    try:
                        with open(config_path, "r") as f:
                            config_data = json.load(f)

                        ssid = config_data.get("ssid")
                        password = config_data.get("password")

                        if ssid and password:
                            if self.logger:
                                self.logger.info(
                                    f"Network config loaded from {config_path}"
                                )
                            return (ssid, password)

                    except (json.JSONDecodeError, PermissionError) as e:
                        if self.logger:
                            self.logger.warning(
                                f"Could not load from {config_path}: {e}"
                            )
                        continue

            if self.logger:
                self.logger.debug("No network configuration found")

            return None

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to load network config: {e}")
            return None

    def clear_network_config(self) -> bool:
        """Clear saved network configuration"""
        try:
            cleared = False

            config_paths = [
                self.config_base_dir / self.network_config_file,
                self.user_config_dir / self.network_config_file,
                Path("config") / self.network_config_file,
            ]

            for config_path in config_paths:
                if config_path.exists():
                    try:
                        config_path.unlink()
                        if self.logger:
                            self.logger.info(
                                f"Network config cleared from {config_path}"
                            )
                        cleared = True
                    except (PermissionError, OSError) as e:
                        if self.logger:
                            self.logger.warning(f"Could not clear {config_path}: {e}")

            if not cleared and self.logger:
                self.logger.debug("No network configuration to clear")

            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to clear network config: {e}")
            return False

    def has_network_config(self) -> bool:
        """Check if network config exists"""
        config_paths = [
            self.config_base_dir / self.network_config_file,
            self.user_config_dir / self.network_config_file,
            Path("config") / self.network_config_file,
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, "r") as f:
                        config_data = json.load(f)

                    if config_data.get("ssid") and config_data.get("password"):
                        return True

                except (json.JSONDecodeError, PermissionError):
                    continue

        return False
