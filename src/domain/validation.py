"""
Validation services for the provisioning system
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from ..interfaces import ILogger, IValidationService
from .errors import ErrorCode, ErrorSeverity, ValidationError


class ValidationService(IValidationService):
    """Central validation service for all domain objects"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger

    def validate_wifi_credentials(
        self,
        ssid: str,
        password: str,
        security_type: str = "WPA2",
        enterprise: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, List[str]]:
        """Validate WiFi credentials with enhanced security checks"""
        errors = []

        # SSID validation with enhanced security checks
        if not ssid or not ssid.strip():
            errors.append("SSID cannot be empty")
        elif len(ssid) > 32:
            errors.append("SSID must be 32 characters or less")
        elif len(ssid) < 1:
            errors.append("SSID must be at least 1 character")

        # Enhanced SSID security validation with whitelist approach
        if ssid:
            # Implement whitelist-based validation instead of blacklist
            # Only allow alphanumeric characters, spaces, hyphens, underscores, and dots
            allowed_pattern = r"^[a-zA-Z0-9\s._-]+$"
            if not re.match(allowed_pattern, ssid):
                errors.append("SSID contains invalid characters. Only letters, numbers, spaces, dots, hyphens, and underscores are allowed")
            
            # Additional length and format checks
            if len(ssid.strip()) != len(ssid):
                errors.append("SSID cannot start or end with whitespace")
            
            if '..' in ssid or '--' in ssid or '__' in ssid:
                errors.append("SSID cannot contain consecutive special characters")
            
            # Check for control characters (comprehensive)
            if any(ord(char) < 32 or ord(char) == 127 for char in ssid):
                errors.append("SSID contains control characters")
            
            # Check for non-printable characters
            if any(not char.isprintable() for char in ssid):
                errors.append("SSID contains non-printable characters")
            
            # Prevent homograph attacks (basic check)
            suspicious_unicode = [
                '\u200B',  # Zero width space
                '\u200C',  # Zero width non-joiner
                '\u200D',  # Zero width joiner
                '\uFEFF',  # Zero width no-break space
            ]
            if any(char in ssid for char in suspicious_unicode):
                errors.append("SSID contains suspicious Unicode characters")
            
            # Additional security patterns (still check these but with better context)
            if self._contains_injection_patterns(ssid):
                errors.append("SSID contains potentially malicious patterns")

            # Check for network configuration injection patterns
            network_patterns = [
                r"\n|\r",  # Line breaks that could break config files
                r"\\[nr]",  # Escaped line breaks
                r"#.*config",  # Configuration directives
            ]
            for pattern in network_patterns:
                if re.search(pattern, ssid, re.IGNORECASE):
                    errors.append(
                        "SSID contains network configuration injection patterns"
                    )
                    break

        # Password validation with enhanced security
        if not password:
            errors.append("Password cannot be empty")
        elif len(password) < 8:
            errors.append("Password must be at least 8 characters")
        elif len(password) > 64:
            errors.append("Password must be 64 characters or less")

        # Enhanced password security validation
        if password:
            # Check for common weak passwords (expanded list)
            weak_passwords = [
                "password",
                "12345678",
                "admin123",
                "password123",
                "qwerty123",
                "letmein",
                "welcome",
                "monkey123",
                "dragon123",
                "master123",
                "shadow123",
                "abc12345",
                "password1",
                "123456789",
                "iloveyou",
            ]
            if password.lower() in weak_passwords:
                errors.append("Password is too weak - commonly used password")

            # Check for password injection patterns
            if re.search(r"['\";\\]", password):
                errors.append("Password contains potentially dangerous characters")

            # Check password complexity
            complexity_score = 0
            if re.search(r"[a-z]", password):
                complexity_score += 1
            if re.search(r"[A-Z]", password):
                complexity_score += 1
            if re.search(r"[0-9]", password):
                complexity_score += 1
            if re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~]", password):
                complexity_score += 1

            if complexity_score < 3 and len(password) < 12:
                errors.append(
                    "Password should contain at least 3 different character types (uppercase, lowercase, numbers, symbols) or be at least 12 characters long"
                )

        # Security type validation
        valid_security_types = [
            "WPA2",
            "WPA3",
            "WEP",
            "OPEN",
            "WPA2-Enterprise",
            "WPA3-Enterprise",
        ]
        if security_type not in valid_security_types:
            errors.append(
                f"Invalid security type. Must be one of: {', '.join(valid_security_types)}"
            )

        # Enterprise WiFi validation
        if security_type in ["WPA2-Enterprise", "WPA3-Enterprise"]:
            if not enterprise:
                errors.append(
                    "Enterprise configuration required for WPA2/WPA3-Enterprise"
                )
            else:
                # Validate enterprise fields
                if not enterprise.get("identity"):
                    errors.append("Enterprise identity is required")
                elif len(enterprise["identity"]) > 128:
                    errors.append("Enterprise identity must be 128 characters or less")

                # Check for injection in identity
                if enterprise.get("identity") and re.search(
                    r"['\";\\]", enterprise["identity"]
                ):
                    errors.append(
                        "Enterprise identity contains potentially dangerous characters"
                    )

                # Certificate validation (basic checks)
                if enterprise.get("ca_cert"):
                    if not enterprise["ca_cert"].startswith(
                        "-----BEGIN CERTIFICATE-----"
                    ):
                        errors.append("CA certificate appears to be invalid format")

                if enterprise.get("client_cert"):
                    if not enterprise["client_cert"].startswith(
                        "-----BEGIN CERTIFICATE-----"
                    ):
                        errors.append("Client certificate appears to be invalid format")

                if enterprise.get("private_key"):
                    if not enterprise["private_key"].startswith("-----BEGIN"):
                        errors.append("Private key appears to be invalid format")

        is_valid = len(errors) == 0

        if self.logger and not is_valid:
            self.logger.warning(f"WiFi credential validation failed: {errors}")

        return is_valid, errors

    def validate_device_pin(self, pin: str) -> Tuple[bool, List[str]]:
        """Validate device PIN"""
        errors = []

        if not pin:
            errors.append("PIN cannot be empty")
            return False, errors

        # PIN should be numeric
        if not pin.isdigit():
            errors.append("PIN must contain only digits")

        # PIN length validation
        if len(pin) < 4:
            errors.append("PIN must be at least 4 digits")
        elif len(pin) > 8:
            errors.append("PIN must be 8 digits or less")

        # Check for weak patterns
        if len(set(pin)) == 1:  # All same digits
            errors.append("PIN cannot be all the same digit")

        # Sequential patterns
        if pin in ["1234", "4321", "0123", "3210"]:
            errors.append("PIN cannot be a sequential pattern")

        is_valid = len(errors) == 0

        if self.logger and not is_valid:
            self.logger.warning(f"Device PIN validation failed: {errors}")

        return is_valid, errors

    def validate_device_name(self, name: str) -> Tuple[bool, List[str]]:
        """Validate device name"""
        errors = []

        if not name or not name.strip():
            errors.append("Device name cannot be empty")
            return False, errors

        name = name.strip()

        # Length validation
        if len(name) < 2:
            errors.append("Device name must be at least 2 characters")
        elif len(name) > 32:
            errors.append("Device name must be 32 characters or less")

        # Character validation (alphanumeric, spaces, hyphens, underscores)
        if not re.match(r"^[a-zA-Z0-9\s\-_]+$", name):
            errors.append(
                "Device name can only contain letters, numbers, spaces, hyphens, and underscores"
            )

        is_valid = len(errors) == 0

        if self.logger and not is_valid:
            self.logger.warning(f"Device name validation failed: {errors}")

        return is_valid, errors

    def validate_ble_data(
        self, data: bytes, max_size: int = 512
    ) -> Tuple[bool, List[str]]:
        """Validate BLE data payload"""
        errors = []

        if not data:
            errors.append("BLE data cannot be empty")
            return False, errors

        # Size validation
        if len(data) > max_size:
            errors.append(f"BLE data exceeds maximum size of {max_size} bytes")

        # Check for suspicious patterns
        suspicious_patterns = [
            b"\x00" * 50,  # Too many null bytes
            b"\xFF" * 50,  # Too many 0xFF bytes
        ]

        for pattern in suspicious_patterns:
            if pattern in data:
                errors.append("BLE data contains suspicious patterns")
                break

        is_valid = len(errors) == 0

        if self.logger and not is_valid:
            self.logger.warning(f"BLE data validation failed: {errors}")

        return is_valid, errors

    def validate_json_data(
        self, json_str: str
    ) -> Tuple[bool, List[str], Optional[Dict[str, Any]]]:
        """Validate and parse JSON data"""
        errors = []
        parsed_data = None

        if not json_str or not json_str.strip():
            errors.append("JSON data cannot be empty")
            return False, errors, None

        try:
            import json

            parsed_data = json.loads(json_str)

            # Additional validation for provisioning data
            if isinstance(parsed_data, dict):
                required_fields = ["ssid", "password"]
                for field in required_fields:
                    if field not in parsed_data:
                        errors.append(f"Missing required field: {field}")
                    elif not isinstance(parsed_data[field], str):
                        errors.append(f"Field {field} must be a string")
            else:
                errors.append("JSON data must be an object")

        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON format: {str(e)}")

        is_valid = len(errors) == 0

        if self.logger and not is_valid:
            self.logger.warning(f"JSON validation failed: {errors}")

        return is_valid, errors, parsed_data

    def validate_ip_address(self, ip: str) -> Tuple[bool, List[str]]:
        """Validate IP address format"""
        errors = []

        if not ip:
            errors.append("IP address cannot be empty")
            return False, errors

        # Basic IPv4 validation
        ip_pattern = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
        match = re.match(ip_pattern, ip)

        if not match:
            errors.append("Invalid IP address format")
        else:
            # Check each octet is in valid range
            for octet in match.groups():
                if int(octet) > 255:
                    errors.append("IP address octet exceeds 255")
                    break

        is_valid = len(errors) == 0

        if self.logger and not is_valid:
            self.logger.warning(f"IP address validation failed: {errors}")

        return is_valid, errors

    def validate_mac_address(self, mac: str) -> Tuple[bool, List[str]]:
        """Validate MAC address format"""
        errors = []

        if not mac:
            errors.append("MAC address cannot be empty")
            return False, errors

        # Standard MAC address format (XX:XX:XX:XX:XX:XX)
        mac_pattern = r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$"

        if not re.match(mac_pattern, mac):
            errors.append("Invalid MAC address format")

        is_valid = len(errors) == 0

        if self.logger and not is_valid:
            self.logger.warning(f"MAC address validation failed: {errors}")

        return is_valid, errors

    def validate_ssid(self, ssid: str) -> bool:
        """Validate network SSID"""
        is_valid, _ = self.validate_wifi_credentials(ssid, "dummy_password")
        # We only care about SSID validation here
        errors = []

        if not ssid or not ssid.strip():
            return False
        elif len(ssid) > 32:
            return False
        elif len(ssid) < 1:
            return False

        # Check for invalid SSID characters
        if re.search(r"[^\x20-\x7E]", ssid):
            return False

        return True

    def validate_password(self, password: str) -> bool:
        """Validate network password"""
        if not password:
            return False
        elif len(password) < 8:
            return False
        elif len(password) > 64:
            return False

        # Check for common weak passwords
        weak_passwords = ["password", "12345678", "admin123", "password123"]
        if password.lower() in weak_passwords:
            return False

        return True

    def validate_credentials(self, ssid: str, password: str) -> bool:
        """Validate complete network credentials"""
        is_valid, _ = self.validate_wifi_credentials(ssid, password)
        return is_valid
    
    def _contains_injection_patterns(self, text: str) -> bool:
        """Check for various injection attack patterns"""
        try:
            # SQL injection patterns
            sql_patterns = [
                r"['\"`;]",  # SQL injection quotes and terminators
                r"\b(union|select|insert|update|delete|drop|exec|alter|create)\b",  # SQL keywords
                r"--\s*",  # SQL comments
                r"/\*.*\*/",  # SQL block comments
                r"\|\|",  # SQL concatenation
            ]
            
            # Command injection patterns
            command_patterns = [
                r"[;&|`$()]",  # Shell metacharacters
                r"\$\(",  # Command substitution
                r"`.*`",  # Backtick command substitution
                r"\\x[0-9a-fA-F]{2}",  # Hex escape sequences
                r"\$\{.*\}",  # Variable expansion
                r"&&|\|\|",  # Command chaining
            ]
            
            # LDAP injection patterns
            ldap_patterns = [
                r"[()&|!]",  # LDAP special characters
                r"\*",  # LDAP wildcards
            ]
            
            # XSS patterns (for completeness)
            xss_patterns = [
                r"<script",  # Script tags
                r"javascript:",  # JavaScript protocol
                r"on\w+\s*=",  # Event handlers
            ]
            
            all_patterns = sql_patterns + command_patterns + ldap_patterns + xss_patterns
            
            for pattern in all_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    if self.logger:
                        self.logger.warning(f"Injection pattern detected: {pattern}")
                    return True
                    
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error checking injection patterns: {e}")
            return True  # Assume malicious if check fails
