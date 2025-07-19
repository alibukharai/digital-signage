"""
Configuration validation and security for the provisioning system
"""

import json
import os
import stat
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import hmac

from ..common.result_handling import Result
from .errors import ErrorCode, ErrorSeverity, ValidationError
from ..interfaces import ILogger


class ConfigurationValidator:
    """Validates configuration files and ensures security compliance"""
    
    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self._required_sections = {
            'security', 'hardware', 'timeouts', 'ble', 'display', 'network'
        }
        self._sensitive_keys = {
            'password', 'key', 'secret', 'token', 'credential', 'auth'
        }
    
    def validate_config_file(self, config_path: str) -> Result[Dict[str, Any], Exception]:
        """Validate configuration file with comprehensive security checks"""
        try:
            config_path = Path(config_path)
            
            # Check file existence
            if not config_path.exists():
                return Result.failure(
                    ValidationError(
                        ErrorCode.CONFIG_FILE_NOT_FOUND,
                        f"Configuration file not found: {config_path}",
                        ErrorSeverity.CRITICAL
                    )
                )
            
            # Validate file permissions
            permission_result = self._validate_file_permissions(config_path)
            if not permission_result.is_success():
                return permission_result
            
            # Load and parse configuration
            try:
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
            except json.JSONDecodeError as e:
                return Result.failure(
                    ValidationError(
                        ErrorCode.CONFIG_PARSE_ERROR,
                        f"Invalid JSON in configuration file: {e}",
                        ErrorSeverity.HIGH
                    )
                )
            
            # Validate configuration structure
            structure_result = self._validate_config_structure(config_data)
            if not structure_result.is_success():
                return structure_result
            
            # Security validation
            security_result = self._validate_security_settings(config_data)
            if not security_result.is_success():
                return security_result
            
            # Environment variable validation
            env_result = self._validate_environment_variables(config_data)
            if not env_result.is_success():
                return env_result
            
            if self.logger:
                self.logger.info(f"Configuration file validated successfully: {config_path}")
            
            return Result.success(config_data)
            
        except Exception as e:
            return Result.failure(
                ValidationError(
                    ErrorCode.CONFIG_VALIDATION_ERROR,
                    f"Configuration validation failed: {e}",
                    ErrorSeverity.HIGH
                )
            )
    
    def _validate_file_permissions(self, config_path: Path) -> Result[bool, Exception]:
        """Validate file permissions for security"""
        try:
            file_stat = config_path.stat()
            file_mode = stat.filemode(file_stat.st_mode)
            
            # Check if file is readable by others
            if file_stat.st_mode & (stat.S_IRGRP | stat.S_IROTH):
                if self.logger:
                    self.logger.warning(f"Configuration file {config_path} is readable by group/others: {file_mode}")
                
                # Try to fix permissions
                try:
                    config_path.chmod(0o600)  # Owner read/write only
                    if self.logger:
                        self.logger.info(f"Fixed permissions for {config_path}")
                except OSError as e:
                    return Result.failure(
                        ValidationError(
                            ErrorCode.CONFIG_PERMISSION_ERROR,
                            f"Cannot fix insecure file permissions: {e}",
                            ErrorSeverity.HIGH
                        )
                    )
            
            # Check ownership (should be current user or root)
            current_uid = os.getuid()
            if file_stat.st_uid not in (current_uid, 0):
                return Result.failure(
                    ValidationError(
                        ErrorCode.CONFIG_PERMISSION_ERROR,
                        f"Configuration file owned by unexpected user (UID: {file_stat.st_uid})",
                        ErrorSeverity.HIGH
                    )
                )
            
            return Result.success(True)
            
        except Exception as e:
            return Result.failure(
                ValidationError(
                    ErrorCode.CONFIG_PERMISSION_ERROR,
                    f"Permission validation failed: {e}",
                    ErrorSeverity.HIGH
                )
            )
    
    def _validate_config_structure(self, config: Dict[str, Any]) -> Result[bool, Exception]:
        """Validate configuration structure and required sections"""
        errors = []
        
        # Check version
        if 'version' not in config:
            errors.append("Missing version field")
        else:
            version = str(config['version'])
            if not re.match(r'^\d+\.\d+$', version):
                errors.append(f"Invalid version format: {version}")
        
        # Check required sections
        missing_sections = self._required_sections - set(config.keys())
        if missing_sections:
            errors.append(f"Missing required sections: {', '.join(missing_sections)}")
        
        # Validate timeout values
        if 'timeouts' in config:
            timeout_errors = self._validate_timeout_values(config['timeouts'])
            errors.extend(timeout_errors)
        
        # Validate security settings structure
        if 'security' in config:
            security_errors = self._validate_security_structure(config['security'])
            errors.extend(security_errors)
        
        if errors:
            return Result.failure(
                ValidationError(
                    ErrorCode.CONFIG_STRUCTURE_ERROR,
                    f"Configuration structure validation failed: {'; '.join(errors)}",
                    ErrorSeverity.HIGH
                )
            )
        
        return Result.success(True)
    
    def _validate_timeout_values(self, timeouts: Dict[str, Any]) -> List[str]:
        """Validate timeout configuration values"""
        errors = []
        
        required_timeouts = {
            'network_scan_timeout', 'connection_timeout', 'health_check_timeout'
        }
        
        for timeout_key in required_timeouts:
            if timeout_key not in timeouts:
                errors.append(f"Missing timeout: {timeout_key}")
                continue
            
            value = timeouts[timeout_key]
            if not isinstance(value, (int, float)) or value <= 0:
                errors.append(f"Invalid timeout value for {timeout_key}: {value}")
            elif value > 3600:  # 1 hour max
                errors.append(f"Timeout too large for {timeout_key}: {value}s")
        
        return errors
    
    def _validate_security_structure(self, security: Dict[str, Any]) -> List[str]:
        """Validate security configuration structure"""
        errors = []
        
        required_security_sections = {
            'config_validation', 'encryption', 'authentication'
        }
        
        for section in required_security_sections:
            if section not in security:
                errors.append(f"Missing security section: {section}")
        
        # Validate encryption settings
        if 'encryption' in security:
            encryption = security['encryption']
            if 'key_derivation_iterations' in encryption:
                iterations = encryption['key_derivation_iterations']
                if not isinstance(iterations, int) or iterations < 10000:
                    errors.append(f"Insufficient key derivation iterations: {iterations}")
        
        # Validate authentication settings
        if 'authentication' in security:
            auth = security['authentication']
            if 'max_failed_attempts' in auth:
                attempts = auth['max_failed_attempts']
                if not isinstance(attempts, int) or attempts < 1 or attempts > 10:
                    errors.append(f"Invalid max_failed_attempts: {attempts}")
        
        return errors
    
    def _validate_security_settings(self, config: Dict[str, Any]) -> Result[bool, Exception]:
        """Validate security-specific configuration settings"""
        try:
            security_issues = []
            
            # Check for plaintext credentials
            plaintext_creds = self._scan_for_plaintext_credentials(config)
            if plaintext_creds:
                security_issues.extend(plaintext_creds)
            
            # Validate BLE security settings
            if 'ble' in config:
                ble_issues = self._validate_ble_security(config['ble'])
                security_issues.extend(ble_issues)
            
            # Validate network security
            if 'security' in config and 'network_security' in config['security']:
                net_issues = self._validate_network_security(config['security']['network_security'])
                security_issues.extend(net_issues)
            
            if security_issues:
                return Result.failure(
                    ValidationError(
                        ErrorCode.CONFIG_SECURITY_ERROR,
                        f"Security validation failed: {'; '.join(security_issues)}",
                        ErrorSeverity.CRITICAL
                    )
                )
            
            return Result.success(True)
            
        except Exception as e:
            return Result.failure(
                ValidationError(
                    ErrorCode.CONFIG_SECURITY_ERROR,
                    f"Security validation error: {e}",
                    ErrorSeverity.CRITICAL
                )
            )
    
    def _scan_for_plaintext_credentials(self, config: Dict[str, Any]) -> List[str]:
        """Scan configuration for plaintext credentials"""
        issues = []
        
        def scan_dict(d: dict, path: str = ""):
            for key, value in d.items():
                current_path = f"{path}.{key}" if path else key
                
                # Check if key suggests sensitive data
                if any(sensitive in key.lower() for sensitive in self._sensitive_keys):
                    if isinstance(value, str) and value and not value.startswith("${"):
                        issues.append(f"Potential plaintext credential at {current_path}")
                
                # Recursively check nested dictionaries
                if isinstance(value, dict):
                    scan_dict(value, current_path)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            scan_dict(item, f"{current_path}[{i}]")
        
        scan_dict(config)
        return issues
    
    def _validate_ble_security(self, ble_config: Dict[str, Any]) -> List[str]:
        """Validate BLE security configuration"""
        issues = []
        
        # Check for security-related BLE settings
        if 'security_level' not in ble_config:
            issues.append("Missing BLE security_level configuration")
        
        if 'pairing_required' not in ble_config:
            issues.append("Missing BLE pairing_required setting")
        elif not ble_config.get('pairing_required', False):
            issues.append("BLE pairing not required - security risk")
        
        # Check advertising timeout
        if 'advertising_timeout' in ble_config:
            timeout = ble_config['advertising_timeout']
            if timeout > 1800:  # 30 minutes
                issues.append(f"BLE advertising timeout too long: {timeout}s")
        
        return issues
    
    def _validate_network_security(self, net_security: Dict[str, Any]) -> List[str]:
        """Validate network security configuration"""
        issues = []
        
        # Check TLS version
        if 'min_tls_version' in net_security:
            tls_version = net_security['min_tls_version']
            if tls_version < "1.2":
                issues.append(f"Minimum TLS version too low: {tls_version}")
        
        # Check certificate validation
        if not net_security.get('validate_certificates', False):
            issues.append("Certificate validation disabled - security risk")
        
        return issues
    
    def _validate_environment_variables(self, config: Dict[str, Any]) -> Result[bool, Exception]:
        """Validate environment variable references"""
        try:
            missing_vars = []
            
            def check_env_vars(d: dict, path: str = ""):
                for key, value in d.items():
                    current_path = f"{path}.{key}" if path else key
                    
                    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                        env_var = value[2:-1]
                        if env_var not in os.environ:
                            missing_vars.append(f"Environment variable {env_var} (referenced at {current_path}) not set")
                    elif isinstance(value, dict):
                        check_env_vars(value, current_path)
            
            check_env_vars(config)
            
            if missing_vars:
                return Result.failure(
                    ValidationError(
                        ErrorCode.CONFIG_ENV_ERROR,
                        f"Missing environment variables: {'; '.join(missing_vars)}",
                        ErrorSeverity.HIGH
                    )
                )
            
            return Result.success(True)
            
        except Exception as e:
            return Result.failure(
                ValidationError(
                    ErrorCode.CONFIG_ENV_ERROR,
                    f"Environment variable validation failed: {e}",
                    ErrorSeverity.HIGH
                )
            )
    
    def generate_config_hash(self, config: Dict[str, Any]) -> str:
        """Generate a hash of the configuration for integrity checking"""
        config_str = json.dumps(config, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(config_str.encode('utf-8')).hexdigest()
    
    def verify_config_integrity(self, config: Dict[str, Any], expected_hash: str) -> bool:
        """Verify configuration integrity using hash"""
        actual_hash = self.generate_config_hash(config)
        return hmac.compare_digest(actual_hash, expected_hash)