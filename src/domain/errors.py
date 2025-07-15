"""
Error handling and exceptions for the provisioning system
"""

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(Enum):
    """Error codes for the provisioning system"""

    UNKNOWN_ERROR = "UNKNOWN_ERROR"

    # Network errors
    NETWORK_SCAN_FAILED = "NETWORK_SCAN_FAILED"
    NETWORK_CONNECTION_FAILED = "NETWORK_CONNECTION_FAILED"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"

    # BLE errors
    BLE_INIT_FAILED = "BLE_INIT_FAILED"
    BLE_ADVERTISING_FAILED = "BLE_ADVERTISING_FAILED"
    BLE_CONNECTION_FAILED = "BLE_CONNECTION_FAILED"
    BLE_DATA_INVALID = "BLE_DATA_INVALID"

    # Display errors
    DISPLAY_INIT_FAILED = "DISPLAY_INIT_FAILED"
    QR_CODE_GENERATION_FAILED = "QR_CODE_GENERATION_FAILED"

    # Security errors
    ENCRYPTION_FAILED = "ENCRYPTION_FAILED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"

    # System errors
    DEVICE_INFO_UNAVAILABLE = "DEVICE_INFO_UNAVAILABLE"
    CONFIG_LOAD_FAILED = "CONFIG_LOAD_FAILED"
    CONFIG_WRITE_FAILED = "CONFIG_WRITE_FAILED"
    CONFIG_READ_FAILED = "CONFIG_READ_FAILED"
    HARDWARE_ERROR = "HARDWARE_ERROR"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"

    # Factory reset errors
    FACTORY_RESET_FAILED = "FACTORY_RESET_FAILED"
    FACTORY_RESET_UNAUTHORIZED = "FACTORY_RESET_UNAUTHORIZED"


class ErrorSeverity(Enum):
    """Error severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProvisioningError(Exception):
    """Base exception for provisioning system errors"""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        self.code = code
        self.message = message
        self.severity = severity
        self.details = details or {}
        self.cause = cause

        super().__init__(f"{code.value}: {message}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary"""
        return {
            "code": self.code.value,
            "message": self.message,
            "severity": self.severity.value,
            "details": self.details,
        }


class NetworkError(ProvisioningError):
    """Network-related errors"""

    pass


class BLEError(ProvisioningError):
    """BLE-related errors"""

    pass


class SecurityError(ProvisioningError):
    """Security-related errors"""

    pass


class DisplayError(ProvisioningError):
    """Display-related errors"""

    pass


class SystemError(ProvisioningError):
    """System-related errors"""

    pass


class ValidationError(ProvisioningError):
    """Validation-related errors"""

    pass


class ConfigurationError(ProvisioningError):
    """Exception raised for configuration-related errors."""

    def __init__(self, message: str, code: int = None, severity: str = None):
        super().__init__(message, code, severity)
