"""
Validation services for the provisioning system
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from ..interfaces import ILogger
from .errors import ValidationError, ErrorCode, ErrorSeverity


class ValidationService:
    """Central validation service for all domain objects"""
    
    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
    
    def validate_wifi_credentials(self, ssid: str, password: str) -> Tuple[bool, List[str]]:
        """Validate WiFi credentials"""
        errors = []
        
        # SSID validation
        if not ssid or not ssid.strip():
            errors.append("SSID cannot be empty")
        elif len(ssid) > 32:
            errors.append("SSID must be 32 characters or less")
        elif len(ssid) < 1:
            errors.append("SSID must be at least 1 character")
        
        # Check for invalid SSID characters
        if re.search(r'[^\x20-\x7E]', ssid):
            errors.append("SSID contains invalid characters")
        
        # Password validation
        if not password:
            errors.append("Password cannot be empty")
        elif len(password) < 8:
            errors.append("Password must be at least 8 characters")
        elif len(password) > 64:
            errors.append("Password must be 64 characters or less")
        
        # Check for common weak passwords
        weak_passwords = ['password', '12345678', 'admin123', 'password123']
        if password.lower() in weak_passwords:
            errors.append("Password is too weak")
        
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
        if pin in ['1234', '4321', '0123', '3210']:
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
        if not re.match(r'^[a-zA-Z0-9\s\-_]+$', name):
            errors.append("Device name can only contain letters, numbers, spaces, hyphens, and underscores")
        
        is_valid = len(errors) == 0
        
        if self.logger and not is_valid:
            self.logger.warning(f"Device name validation failed: {errors}")
        
        return is_valid, errors
    
    def validate_ble_data(self, data: bytes, max_size: int = 512) -> Tuple[bool, List[str]]:
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
            b'\x00' * 50,  # Too many null bytes
            b'\xFF' * 50,  # Too many 0xFF bytes
        ]
        
        for pattern in suspicious_patterns:
            if pattern in data:
                errors.append("BLE data contains suspicious patterns")
                break
        
        is_valid = len(errors) == 0
        
        if self.logger and not is_valid:
            self.logger.warning(f"BLE data validation failed: {errors}")
        
        return is_valid, errors
    
    def validate_json_data(self, json_str: str) -> Tuple[bool, List[str], Optional[Dict[str, Any]]]:
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
                required_fields = ['ssid', 'password']
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
        ip_pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
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
        mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        
        if not re.match(mac_pattern, mac):
            errors.append("Invalid MAC address format")
        
        is_valid = len(errors) == 0
        
        if self.logger and not is_valid:
            self.logger.warning(f"MAC address validation failed: {errors}")
        
        return is_valid, errors
