"""
Ownership service implementation with consistent error handling using Result pattern
"""

import hashlib
import json
import secrets
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..common.result_handling import Result
from ..domain.configuration import SecurityConfig
from ..domain.errors import ErrorCode, ErrorSeverity, SecurityError
from ..interfaces import ILogger, IOwnershipService


class OwnershipService(IOwnershipService):
    """Concrete implementation of ownership service"""

    def __init__(self, config: SecurityConfig, logger: Optional[ILogger] = None):
        self.config = config
        self.logger = logger

        # Use more accessible paths
        try:
            # Try config directory first
            config_dir = Path("config")
            config_dir.mkdir(parents=True, exist_ok=True)
            self.owner_file = config_dir / "owner.json"
            self.backup_file = (
                Path.home() / ".config" / "rockpi-provisioning" / "owner.json"
            )
        except PermissionError:
            # Fallback to user directory only
            user_config_dir = Path.home() / ".config" / "rockpi-provisioning"
            user_config_dir.mkdir(parents=True, exist_ok=True)
            self.owner_file = user_config_dir / "owner.json"
            self.backup_file = self.owner_file  # Same as primary in this case

        # Setup mode tracking
        self.setup_mode_active = False
        self.setup_start_time: Optional[float] = None
        self.setup_token: Optional[str] = None

        if self.logger:
            self.logger.info(
                f"Ownership service initialized, owner file: {self.owner_file}"
            )

    def is_owner_registered(self) -> bool:
        """Check if owner is registered"""
        try:
            for owner_file in [self.owner_file, self.backup_file]:
                if owner_file.exists():
                    try:
                        with open(owner_file, "r") as f:
                            owner_data = json.load(f)

                        # Check if we have valid owner data
                        if (
                            owner_data.get("pin_hash")
                            and owner_data.get("owner_name")
                            and owner_data.get("registered_at")
                        ):
                            return True

                    except (json.JSONDecodeError, PermissionError):
                        continue

            return False

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error checking owner registration: {e}")
            return False

    def register_owner(self, pin: str, name: str) -> Result[bool, Exception]:
        """Register device owner using Result pattern for consistent error handling"""
        try:
            # Check if setup mode is active
            if not self.setup_mode_active:
                return Result.failure(
                    SecurityError(
                        ErrorCode.AUTHENTICATION_FAILED,
                        "Setup mode not active",
                        ErrorSeverity.MEDIUM,
                    )
                )

            # Check setup timeout
            if (
                self.setup_start_time
                and time.time() - self.setup_start_time
                > self.config.owner_setup_timeout
            ):
                self.setup_mode_active = False
                return Result.failure(
                    SecurityError(
                        ErrorCode.AUTHENTICATION_FAILED,
                        "Setup mode timed out",
                        ErrorSeverity.MEDIUM,
                    )
                )

            # Validate PIN
            if not self._validate_pin(pin):
                return Result.failure(
                    SecurityError(
                        ErrorCode.AUTHENTICATION_FAILED,
                        "Invalid PIN format",
                        ErrorSeverity.MEDIUM,
                    )
                )

            # Validate name
            if not name or len(name.strip()) < 2:
                return Result.failure(
                    SecurityError(
                        ErrorCode.AUTHENTICATION_FAILED,
                        "Invalid owner name",
                        ErrorSeverity.MEDIUM,
                    )
                )

            # Check if owner already registered
            if self.is_owner_registered():
                return Result.failure(
                    SecurityError(
                        ErrorCode.AUTHENTICATION_FAILED,
                        "Owner already registered",
                        ErrorSeverity.MEDIUM,
                    )
                )

            # Hash the PIN
            pin_hash = self._hash_pin(pin)

            # Create owner data
            owner_data = {
                "pin_hash": pin_hash,
                "owner_name": name.strip(),
                "registered_at": time.time(),
                "setup_token": self.setup_token,
                "device_id": self._get_device_id(),
            }

            # Save to both locations
            saved = False
            for owner_file in [self.owner_file, self.backup_file]:
                try:
                    with open(owner_file, "w") as f:
                        json.dump(owner_data, f, indent=2)

                    # Set secure permissions
                    owner_file.chmod(0o600)
                    saved = True

                    if self.logger:
                        self.logger.info(f"Owner registered and saved to {owner_file}")

                except (PermissionError, OSError) as e:
                    if self.logger:
                        self.logger.warning(f"Could not save to {owner_file}: {e}")
                    continue

            if not saved:
                return Result.failure(
                    SecurityError(
                        ErrorCode.CONFIG_WRITE_FAILED,
                        "Failed to save owner data",
                        ErrorSeverity.HIGH,
                    )
                )

            # Clear setup mode
            self.setup_mode_active = False
            self.setup_token = None

            if self.logger:
                self.logger.info(f"Owner '{name}' registered successfully")

            return Result.success(True)

        except Exception as e:
            error_msg = f"Registration failed: {str(e)}"
            if self.logger:
                self.logger.error(f"Owner registration failed: {e}")
            return Result.failure(
                SecurityError(
                    ErrorCode.AUTHENTICATION_FAILED,
                    error_msg,
                    ErrorSeverity.HIGH,
                )
            )

    def authenticate_owner(self, pin: str) -> Result[bool, Exception]:
        """Authenticate owner using Result pattern for consistent error handling"""
        try:
            if not self.is_owner_registered():
                return Result.failure(
                    SecurityError(
                        ErrorCode.AUTHENTICATION_FAILED,
                        "No owner registered",
                        ErrorSeverity.MEDIUM,
                    )
                )

            # Load owner data
            owner_data = self._load_owner_data()
            if not owner_data:
                return Result.failure(
                    SecurityError(
                        ErrorCode.CONFIG_READ_FAILED,
                        "Could not load owner data",
                        ErrorSeverity.HIGH,
                    )
                )

            # Verify PIN
            stored_hash = owner_data.get("pin_hash")
            if not stored_hash:
                return Result.failure(
                    SecurityError(
                        ErrorCode.CONFIG_READ_FAILED,
                        "Invalid owner data",
                        ErrorSeverity.HIGH,
                    )
                )

            if self._verify_pin(pin, stored_hash):
                if self.logger:
                    self.logger.info("Owner authentication successful")
                return Result.success(True)
            else:
                if self.logger:
                    self.logger.warning("Owner authentication failed")
                return Result.failure(
                    SecurityError(
                        ErrorCode.AUTHENTICATION_FAILED,
                        "Invalid PIN",
                        ErrorSeverity.MEDIUM,
                    )
                )

        except Exception as e:
            error_msg = f"Authentication error: {str(e)}"
            if self.logger:
                self.logger.error(f"Owner authentication error: {e}")
            return Result.failure(
                SecurityError(
                    ErrorCode.AUTHENTICATION_FAILED,
                    error_msg,
                    ErrorSeverity.HIGH,
                )
            )

    def start_setup_mode(self) -> Result[bool, Exception]:
        """Start owner setup mode using Result pattern for consistent error handling"""
        try:
            if self.is_owner_registered():
                error_msg = "Cannot start setup mode - owner already registered"
                if self.logger:
                    self.logger.warning(error_msg)
                return Result.failure(
                    SecurityError(
                        ErrorCode.AUTHENTICATION_FAILED,
                        error_msg,
                        ErrorSeverity.MEDIUM,
                    )
                )

            self.setup_mode_active = True
            self.setup_start_time = time.time()
            self.setup_token = secrets.token_urlsafe(16)

            if self.logger:
                self.logger.info(
                    f"Owner setup mode started (timeout: {self.config.owner_setup_timeout}s)"
                )
                self.logger.info(f"Setup token: {self.setup_token}")

            return Result.success(True)

        except Exception as e:
            error_msg = f"Failed to start setup mode: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                SecurityError(
                    ErrorCode.SYSTEM_ERROR,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

    def get_setup_info(self) -> Dict[str, Any]:
        """Get setup mode information"""
        if not self.setup_mode_active:
            return {"active": False}

        remaining_time = 0
        if self.setup_start_time:
            elapsed = time.time() - self.setup_start_time
            remaining_time = max(0, self.config.owner_setup_timeout - elapsed)

        return {
            "active": True,
            "setup_token": self.setup_token,
            "remaining_time_seconds": int(remaining_time),
            "pin_requirements": {
                "min_length": 4,
                "max_length": 8,
                "numeric_only": True,
            },
        }

    def _validate_pin(self, pin: str) -> bool:
        """Validate PIN format"""
        if not pin or not pin.isdigit():
            return False

        if len(pin) < 4 or len(pin) > 8:
            return False

        # Check for weak patterns
        if len(set(pin)) == 1:  # All same digits
            return False

        # Check for sequential patterns
        weak_patterns = ["1234", "4321", "0123", "3210", "1111", "0000"]
        if pin in weak_patterns:
            return False

        return True

    def _hash_pin(self, pin: str) -> str:
        """Hash PIN securely"""
        salt = secrets.token_bytes(32)
        pin_hash = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 100000)
        return salt.hex() + ":" + pin_hash.hex()

    def _verify_pin(self, pin: str, stored_hash: str) -> bool:
        """Verify PIN against stored hash"""
        try:
            salt_hex, hash_hex = stored_hash.split(":")
            salt = bytes.fromhex(salt_hex)
            stored_pin_hash = bytes.fromhex(hash_hex)

            pin_hash = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 100000)

            return pin_hash == stored_pin_hash

        except Exception:
            return False

    def _load_owner_data(self) -> Optional[Dict[str, Any]]:
        """Load owner data from file"""
        for owner_file in [self.owner_file, self.backup_file]:
            if owner_file.exists():
                try:
                    with open(owner_file, "r") as f:
                        return json.load(f)
                except (json.JSONDecodeError, PermissionError):
                    continue
        return None

    def _get_device_id(self) -> str:
        """Get device ID for ownership tracking"""
        try:
            # Try to get machine ID
            try:
                with open("/etc/machine-id", "r") as f:
                    return f.read().strip()
            except FileNotFoundError:
                pass

            # Fallback to generating from system info
            import platform

            return hashlib.sha256(
                f"{platform.node()}{platform.machine()}".encode()
            ).hexdigest()[:16]

        except Exception:
            return "unknown"
