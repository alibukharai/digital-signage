"""
Specification pattern for complex validation rules
Following SOLID principles for extensible validation
"""

import re
from abc import ABC, abstractmethod
from typing import Generic, List, TypeVar, Union

T = TypeVar("T")


class ISpecification(ABC, Generic[T]):
    """Interface for specifications"""

    @abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool:
        """Check if candidate satisfies the specification"""
        pass

    def and_(self, other: "ISpecification[T]") -> "AndSpecification[T]":
        """Combine specifications with AND logic"""
        return AndSpecification(self, other)

    def or_(self, other: "ISpecification[T]") -> "OrSpecification[T]":
        """Combine specifications with OR logic"""
        return OrSpecification(self, other)

    def not_(self) -> "NotSpecification[T]":
        """Negate the specification"""
        return NotSpecification(self)


class AndSpecification(ISpecification[T]):
    """Combines two specifications with AND logic"""

    def __init__(self, left: ISpecification[T], right: ISpecification[T]):
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self.left.is_satisfied_by(candidate) and self.right.is_satisfied_by(
            candidate
        )


class OrSpecification(ISpecification[T]):
    """Combines two specifications with OR logic"""

    def __init__(self, left: ISpecification[T], right: ISpecification[T]):
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self.left.is_satisfied_by(candidate) or self.right.is_satisfied_by(
            candidate
        )


class NotSpecification(ISpecification[T]):
    """Negates a specification"""

    def __init__(self, specification: ISpecification[T]):
        self.specification = specification

    def is_satisfied_by(self, candidate: T) -> bool:
        return not self.specification.is_satisfied_by(candidate)


# Network credential specifications
class ValidSSIDSpecification(ISpecification[str]):
    """Specification for valid SSID"""

    def is_satisfied_by(self, ssid: str) -> bool:
        if not ssid or not ssid.strip():
            return False
        if len(ssid) > 32 or len(ssid) < 1:
            return False
        # Check for invalid characters
        return not re.search(r"[^\x20-\x7E]", ssid)


class StrongPasswordSpecification(ISpecification[str]):
    """Specification for strong passwords"""

    def is_satisfied_by(self, password: str) -> bool:
        if not password:
            return False
        if len(password) < 8 or len(password) > 64:
            return False

        # Check for common weak passwords
        weak_passwords = ["password", "12345678", "admin123", "password123"]
        if password.lower() in weak_passwords:
            return False

        return True


class MinimumLengthSpecification(ISpecification[str]):
    """Specification for minimum length"""

    def __init__(self, min_length: int):
        self.min_length = min_length

    def is_satisfied_by(self, value: str) -> bool:
        return len(value) >= self.min_length


class MaximumLengthSpecification(ISpecification[str]):
    """Specification for maximum length"""

    def __init__(self, max_length: int):
        self.max_length = max_length

    def is_satisfied_by(self, value: str) -> bool:
        return len(value) <= self.max_length


class RegexPatternSpecification(ISpecification[str]):
    """Specification for regex pattern matching"""

    def __init__(self, pattern: str):
        self.pattern = re.compile(pattern)

    def is_satisfied_by(self, value: str) -> bool:
        return bool(self.pattern.match(value))


class NotEmptySpecification(ISpecification[str]):
    """Specification for non-empty strings"""

    def is_satisfied_by(self, value: str) -> bool:
        return bool(value and value.strip())


# Composite specifications for complex validation
class NetworkCredentialsSpecification(ISpecification[dict]):
    """Composite specification for network credentials"""

    def __init__(self):
        # Define SSID specification
        self.ssid_spec = (
            NotEmptySpecification()
            .and_(MinimumLengthSpecification(1))
            .and_(MaximumLengthSpecification(32))
            .and_(ValidSSIDSpecification())
        )

        # Define password specification
        self.password_spec = (
            NotEmptySpecification()
            .and_(MinimumLengthSpecification(8))
            .and_(MaximumLengthSpecification(64))
            .and_(StrongPasswordSpecification())
        )

    def is_satisfied_by(self, credentials: dict) -> bool:
        if not isinstance(credentials, dict):
            return False

        ssid = credentials.get("ssid", "")
        password = credentials.get("password", "")

        return self.ssid_spec.is_satisfied_by(
            ssid
        ) and self.password_spec.is_satisfied_by(password)


class DevicePinSpecification(ISpecification[str]):
    """Specification for device PIN validation"""

    def is_satisfied_by(self, pin: str) -> bool:
        if not pin:
            return False

        # Must be numeric
        if not pin.isdigit():
            return False

        # Length validation
        if len(pin) < 4 or len(pin) > 8:
            return False

        # Check for weak patterns
        if len(set(pin)) == 1:  # All same digits
            return False

        # Sequential patterns
        if pin in ["1234", "4321", "0123", "3210"]:
            return False

        return True


class ValidIPAddressSpecification(ISpecification[str]):
    """Specification for valid IP addresses"""

    def is_satisfied_by(self, ip: str) -> bool:
        if not ip:
            return False

        # Basic IPv4 validation
        ip_pattern = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
        match = re.match(ip_pattern, ip)

        if not match:
            return False

        # Check each octet is in valid range
        for octet in match.groups():
            if int(octet) > 255:
                return False

        return True


class ValidMacAddressSpecification(ISpecification[str]):
    """Specification for valid MAC addresses"""

    def is_satisfied_by(self, mac: str) -> bool:
        if not mac:
            return False

        # Standard MAC address format (XX:XX:XX:XX:XX:XX)
        mac_pattern = r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$"
        return bool(re.match(mac_pattern, mac))


# Factory for creating specifications
class SpecificationFactory:
    """Factory for creating common specifications"""

    @staticmethod
    def create_network_credentials_spec() -> NetworkCredentialsSpecification:
        """Create network credentials specification"""
        return NetworkCredentialsSpecification()

    @staticmethod
    def create_device_pin_spec() -> DevicePinSpecification:
        """Create device PIN specification"""
        return DevicePinSpecification()

    @staticmethod
    def create_ip_address_spec() -> ValidIPAddressSpecification:
        """Create IP address specification"""
        return ValidIPAddressSpecification()

    @staticmethod
    def create_mac_address_spec() -> ValidMacAddressSpecification:
        """Create MAC address specification"""
        return ValidMacAddressSpecification()

    @staticmethod
    def create_length_range_spec(min_len: int, max_len: int) -> ISpecification[str]:
        """Create length range specification"""
        return MinimumLengthSpecification(min_len).and_(
            MaximumLengthSpecification(max_len)
        )


# Enhanced validation service using specifications
class SpecificationBasedValidationService:
    """Validation service using specification pattern"""

    def __init__(self):
        self.factory = SpecificationFactory()

    def validate_network_credentials(self, credentials: dict) -> bool:
        """Validate network credentials using specifications"""
        spec = self.factory.create_network_credentials_spec()
        return spec.is_satisfied_by(credentials)

    def validate_device_pin(self, pin: str) -> bool:
        """Validate device PIN using specifications"""
        spec = self.factory.create_device_pin_spec()
        return spec.is_satisfied_by(pin)

    def validate_ip_address(self, ip: str) -> bool:
        """Validate IP address using specifications"""
        spec = self.factory.create_ip_address_spec()
        return spec.is_satisfied_by(ip)

    def validate_mac_address(self, mac: str) -> bool:
        """Validate MAC address using specifications"""
        spec = self.factory.create_mac_address_spec()
        return spec.is_satisfied_by(mac)

    def create_custom_validation(
        self, *specifications: ISpecification[str]
    ) -> ISpecification[str]:
        """Create custom validation by combining specifications"""
        if not specifications:
            raise ValueError("At least one specification is required")

        result = specifications[0]
        for spec in specifications[1:]:
            result = result.and_(spec)

        return result
