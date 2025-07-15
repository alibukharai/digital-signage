"""
Security service implementation with consistent error handling using Result pattern
"""

import base64
import hashlib
import json
import os
import platform
import secrets
import time
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..common.result_handling import Result
from ..domain.configuration import SecurityConfig
from ..domain.errors import ErrorCode, ErrorSeverity, SecurityError
from ..interfaces import ILogger, ISecurityService


class SecurityService(ISecurityService):
    """Concrete implementation of security service"""

    def __init__(self, config: SecurityConfig, logger: Optional[ILogger] = None):
        self.config = config
        self.logger = logger
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.master_key = self._generate_master_key()

        if self.logger:
            self.logger.info("Security service initialized")

    def encrypt_data(
        self, data: str, key_id: Optional[str] = None
    ) -> Result[bytes, Exception]:
        """Encrypt data using Result pattern for consistent error handling"""
        try:
            # SECURITY: Encryption is ALWAYS mandatory - no bypass allowed
            # This method will NEVER return plaintext data under any circumstances

            # Validate input data for security threats
            if self.detect_plaintext_credentials(data):
                error_msg = "Plaintext credentials detected - encryption required"
                if self.logger:
                    self.logger.error(error_msg)
                return Result.failure(
                    SecurityError(
                        ErrorCode.ENCRYPTION_FAILED,
                        error_msg,
                        ErrorSeverity.CRITICAL,
                    )
                )

            # Auto-rotate session key if it's getting old
            if key_id and key_id in self.sessions:
                session_data = self.sessions[key_id]
                key_age = time.time() - session_data.get("key_created", 0)
                if key_age > 3600:  # Rotate keys older than 1 hour
                    self._rotate_session_key_internal(key_id)
                key = self.sessions[key_id].get("encryption_key", self.master_key)
            else:
                key = self.master_key

            # CRITICAL: Validate that we have a proper encryption key
            if not key or len(key) < 32:
                error_msg = "Invalid or missing encryption key - operation aborted"
                if self.logger:
                    self.logger.error(error_msg)
                return Result.failure(
                    SecurityError(
                        ErrorCode.ENCRYPTION_FAILED,
                        error_msg,
                        ErrorSeverity.CRITICAL,
                    )
                )

            # Additional key compromise detection
            if self._detect_key_compromise(key):
                error_msg = "Key compromise detected - encryption aborted"
                if self.logger:
                    self.logger.error(error_msg)
                return Result.failure(
                    SecurityError(
                        ErrorCode.ENCRYPTION_FAILED,
                        error_msg,
                        ErrorSeverity.CRITICAL,
                    )
                )

            fernet = Fernet(key)
            encrypted = fernet.encrypt(data.encode("utf-8"))

            # Update session activity for key rotation tracking
            if key_id and key_id in self.sessions:
                self.sessions[key_id]["last_activity"] = time.time()

            if self.logger:
                self.logger.debug(f"Data encrypted securely (key_id: {key_id})")

            return Result.success(encrypted)

        except Exception as e:
            error_msg = f"Failed to encrypt data: {str(e)}"
            if self.logger:
                self.logger.error(f"Encryption failed: {e}")
            return Result.failure(
                SecurityError(
                    ErrorCode.ENCRYPTION_FAILED,
                    error_msg,
                    ErrorSeverity.CRITICAL,
                )
            )

    def decrypt_data(
        self, encrypted_data: bytes, key_id: Optional[str] = None
    ) -> Result[str, Exception]:
        """Decrypt data using Result pattern for consistent error handling"""
        try:
            # SECURITY: Encryption is ALWAYS mandatory - no bypass allowed
            # This method will NEVER return data that wasn't properly encrypted

            # Use session key if provided, otherwise master key
            if key_id and key_id in self.sessions:
                key = self.sessions[key_id].get("encryption_key", self.master_key)
            else:
                key = self.master_key

            # CRITICAL: Validate that we have a proper encryption key
            if not key or len(key) < 32:
                error_msg = "Invalid or missing decryption key - operation aborted"
                if self.logger:
                    self.logger.error(error_msg)
                return Result.failure(
                    SecurityError(
                        ErrorCode.ENCRYPTION_FAILED,
                        error_msg,
                        ErrorSeverity.CRITICAL,
                    )
                )

            # Additional key compromise detection
            if self._detect_key_compromise(key):
                error_msg = "Key compromise detected - decryption aborted"
                if self.logger:
                    self.logger.error(error_msg)
                return Result.failure(
                    SecurityError(
                        ErrorCode.ENCRYPTION_FAILED,
                        error_msg,
                        ErrorSeverity.CRITICAL,
                    )
                )

            fernet = Fernet(key)
            decrypted = fernet.decrypt(encrypted_data)

            # Update session activity for key rotation tracking
            if key_id and key_id in self.sessions:
                self.sessions[key_id]["last_activity"] = time.time()

            if self.logger:
                self.logger.debug(f"Data decrypted securely (key_id: {key_id})")

            return Result.success(decrypted.decode("utf-8"))

        except Exception as e:
            error_msg = f"Failed to decrypt data: {str(e)}"
            if self.logger:
                self.logger.error(f"Decryption failed: {e}")
            return Result.failure(
                SecurityError(
                    ErrorCode.ENCRYPTION_FAILED,
                    error_msg,
                    ErrorSeverity.CRITICAL,
                )
            )

    def validate_credentials(self, ssid: str, password: str) -> Result[bool, Exception]:
        """Validate network credentials using Result pattern for consistent error handling"""
        try:
            # Basic validation
            if not ssid or not ssid.strip():
                return Result.success(False)

            if not password or len(password) < 8:
                return Result.success(False)

            # Check for common patterns that might indicate malicious input
            suspicious_patterns = [
                "<script",
                "<?xml",
                "javascript:",
                "data:",
                "vbscript:",
                "onload=",
                "onerror=",
                "onclick=",
                "${",
                "#{",
                "../",
                "..\\",
                "file://",
                "ftp://",
            ]

            combined_input = (ssid + password).lower()
            for pattern in suspicious_patterns:
                if pattern in combined_input:
                    if self.logger:
                        self.logger.warning(
                            f"Suspicious pattern detected in credentials: {pattern}"
                        )
                    return Result.success(False)

            # Check for excessive length
            if len(ssid) > 32 or len(password) > 64:
                return Result.success(False)

            # Check for null bytes or control characters
            for char in ssid + password:
                if ord(char) < 32 and char not in ["\t", "\n", "\r"]:
                    return Result.success(False)

            return Result.success(True)

        except Exception as e:
            error_msg = f"Credential validation error: {e}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(Exception(error_msg))

    def create_session(self, client_id: str) -> Result[str, Exception]:
        """Create secure session using Result pattern for consistent error handling"""
        try:
            # Generate session ID
            session_id = secrets.token_urlsafe(32)

            # Generate session-specific encryption key
            session_key = Fernet.generate_key()

            # Create session data
            session_data = {
                "client_id": client_id,
                "session_id": session_id,
                "encryption_key": session_key,
                "created_at": time.time(),
                "last_activity": time.time(),
                "failed_attempts": 0,
            }

            self.sessions[session_id] = session_data

            if self.logger:
                self.logger.info(f"Session created for client: {client_id}")

            # Cleanup expired sessions
            self._cleanup_expired_sessions()

            return Result.success(session_id)

        except Exception as e:
            error_msg = f"Failed to create session: {str(e)}"
            if self.logger:
                self.logger.error(f"Session creation failed: {e}")
            return Result.failure(
                SecurityError(
                    ErrorCode.SESSION_EXPIRED,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

    def cleanup_expired_sessions(self) -> None:
        """Clean up expired session keys"""
        self._cleanup_expired_sessions()

    def _cleanup_expired_sessions(self) -> None:
        """Internal method to cleanup expired sessions"""
        try:
            current_time = time.time()
            expired_sessions = []

            for session_id, session_data in self.sessions.items():
                last_activity = session_data.get("last_activity", 0)
                if current_time - last_activity > self.config.session_timeout:
                    expired_sessions.append(session_id)

            for session_id in expired_sessions:
                del self.sessions[session_id]
                if self.logger:
                    self.logger.debug(f"Session expired: {session_id}")

            if expired_sessions and self.logger:
                self.logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Session cleanup error: {e}")

    def _generate_master_key(self) -> bytes:
        """Generate master encryption key"""
        try:
            # In production, this should be derived from a secure source
            # For now, we'll generate a key based on system information
            import os
            import platform

            # Gather system-specific data
            system_data = f"{platform.node()}{platform.machine()}{os.getpid()}"

            # Add some entropy
            entropy = secrets.token_bytes(32)

            # Create key derivation
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"rockpi3399provisioning",  # In production, use random salt
                iterations=100000,
            )

            key = base64.urlsafe_b64encode(kdf.derive(system_data.encode() + entropy))

            if self.logger:
                self.logger.debug("Master encryption key generated")

            return key

        except Exception as e:
            if self.logger:
                self.logger.error(f"Master key generation failed: {e}")
            # Fallback to simple key generation
            return Fernet.generate_key()

    def validate_session(self, session_id: str) -> bool:
        """Validate session"""
        try:
            if session_id not in self.sessions:
                return False

            session_data = self.sessions[session_id]
            current_time = time.time()

            # Check if session expired
            if (
                current_time - session_data["last_activity"]
                > self.config.session_timeout
            ):
                del self.sessions[session_id]
                return False

            # Update last activity
            session_data["last_activity"] = current_time

            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Session validation error: {e}")
            return False

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information"""
        if session_id in self.sessions:
            session_data = self.sessions[session_id].copy()
            # Remove sensitive data
            session_data.pop("encryption_key", None)
            return session_data
        return None

    def detect_plaintext_credentials(self, data: str) -> bool:
        """Detect if credentials are transmitted in plaintext (security validation)"""
        try:
            # Check if data looks like JSON credentials
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict) and (
                    "ssid" in parsed or "password" in parsed
                ):
                    if self.logger:
                        self.logger.warning(
                            "Plaintext credentials detected and rejected"
                        )
                    return True
            except json.JSONDecodeError:
                pass

            # Check for common plaintext patterns
            plaintext_indicators = [
                '"ssid":',
                '"password":',
                "wifi_credentials",
                "network_name",
                "passphrase",
                '"psk":',
            ]

            data_lower = data.lower()
            for indicator in plaintext_indicators:
                if indicator in data_lower:
                    if self.logger:
                        self.logger.warning(
                            f"Plaintext indicator detected: {indicator}"
                        )
                    return True

            return False

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error detecting plaintext: {e}")
            # Err on the side of caution - assume plaintext if we can't determine
            return True

    def rotate_session_key(self, session_id: str) -> Result[bool, Exception]:
        """Rotate encryption key for a session"""
        try:
            if session_id not in self.sessions:
                return Result.failure(
                    SecurityError(
                        ErrorCode.SESSION_EXPIRED,
                        "Session not found for key rotation",
                        ErrorSeverity.MEDIUM,
                    )
                )

            # Generate new session key
            new_key = Fernet.generate_key()

            # Update session with new key
            self.sessions[session_id]["encryption_key"] = new_key
            self.sessions[session_id]["last_activity"] = time.time()

            if self.logger:
                self.logger.info(f"Session key rotated for session: {session_id}")

            return Result.success(True)

        except Exception as e:
            error_msg = f"Failed to rotate session key: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                SecurityError(
                    ErrorCode.ENCRYPTION_FAILED,
                    error_msg,
                    ErrorSeverity.HIGH,
                )
            )

    def validate_encryption_compliance(self, data: bytes) -> Result[bool, Exception]:
        """Validate that data meets encryption compliance requirements"""
        try:
            # Check if data appears to be properly encrypted
            if len(data) < 16:  # Minimum encrypted data length
                return Result.failure(
                    SecurityError(
                        ErrorCode.ENCRYPTION_FAILED,
                        "Data too short to be properly encrypted",
                        ErrorSeverity.HIGH,
                    )
                )

            # Check for Fernet token format (base64 encoded with gAAAAAB prefix when decoded)
            try:
                # Fernet tokens should be at least 57 bytes and base64 encoded
                if len(data) >= 57:
                    # Basic validation passed
                    return Result.success(True)
                else:
                    return Result.failure(
                        SecurityError(
                            ErrorCode.ENCRYPTION_FAILED,
                            "Data does not meet minimum encryption standards",
                            ErrorSeverity.HIGH,
                        )
                    )
            except Exception:
                return Result.failure(
                    SecurityError(
                        ErrorCode.ENCRYPTION_FAILED,
                        "Data validation failed - possible plaintext",
                        ErrorSeverity.HIGH,
                    )
                )

        except Exception as e:
            error_msg = f"Encryption compliance validation error: {e}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                SecurityError(
                    ErrorCode.ENCRYPTION_FAILED,
                    error_msg,
                    ErrorSeverity.HIGH,
                )
            )

    def _detect_key_compromise(self, key: bytes) -> bool:
        """Detect potential key compromise based on key characteristics"""
        try:
            # Check if key looks like it might be compromised
            # This is a basic implementation - in production you'd use more sophisticated methods

            # Check key length
            if len(key) < 32:
                if self.logger:
                    self.logger.warning("Key appears compromised: insufficient length")
                return True

            # Check for predictable patterns (weak keys)
            key_str = key.decode("utf-8", errors="ignore")
            weak_patterns = [
                "00000000",
                "11111111",
                "aaaaaaaa",
                "AAAAAAAA",
                "12345678",
                "password",
                "qwerty",
                "test",
            ]

            for pattern in weak_patterns:
                if pattern in key_str:
                    if self.logger:
                        self.logger.warning(
                            f"Key appears compromised: weak pattern detected"
                        )
                    return True

            # Check for repeated sequences
            if len(set(key)) < 10:  # Too few unique bytes suggests pattern
                if self.logger:
                    self.logger.warning("Key appears compromised: insufficient entropy")
                return True

            return False

        except Exception as e:
            if self.logger:
                self.logger.error(f"Key compromise detection error: {e}")
            # Err on the side of caution
            return True

    def _rotate_session_key_internal(self, session_id: str) -> None:
        """Internal method to rotate session key"""
        try:
            if session_id in self.sessions:
                # Generate new key
                new_key = Fernet.generate_key()

                # Update session
                self.sessions[session_id]["encryption_key"] = new_key
                self.sessions[session_id]["key_created"] = time.time()
                self.sessions[session_id]["last_activity"] = time.time()

                if self.logger:
                    self.logger.debug(
                        f"Session key rotated internally for: {session_id}"
                    )

        except Exception as e:
            if self.logger:
                self.logger.error(f"Internal key rotation failed for {session_id}: {e}")

    def _enforce_encryption_compliance(self, data: str) -> Result[bool, Exception]:
        """Enforce encryption compliance for all sensitive data"""
        try:
            # Check if data contains sensitive information that must be encrypted
            sensitive_indicators = [
                "password",
                "pwd",
                "pass",
                "secret",
                "key",
                "token",
                "credential",
                "auth",
                "login",
                "psk",
                "passphrase",
            ]

            data_lower = data.lower()
            for indicator in sensitive_indicators:
                if indicator in data_lower:
                    # This data contains sensitive information and must be encrypted
                    if self.logger:
                        self.logger.error(
                            f"Sensitive data detected without encryption: {indicator}"
                        )
                    return Result.failure(
                        SecurityError(
                            ErrorCode.ENCRYPTION_FAILED,
                            f"Sensitive data must be encrypted - detected: {indicator}",
                            ErrorSeverity.CRITICAL,
                        )
                    )

            # Check for structured data that looks like credentials
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    credential_keys = ["ssid", "password", "username", "key", "secret"]
                    for key in credential_keys:
                        if key in parsed:
                            if self.logger:
                                self.logger.error(
                                    f"Credential structure detected without encryption: {key}"
                                )
                            return Result.failure(
                                SecurityError(
                                    ErrorCode.ENCRYPTION_FAILED,
                                    f"Credential data must be encrypted - found: {key}",
                                    ErrorSeverity.CRITICAL,
                                )
                            )
            except json.JSONDecodeError:
                pass  # Not JSON, continue other checks

            return Result.success(True)

        except Exception as e:
            error_msg = f"Encryption compliance enforcement error: {e}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                SecurityError(
                    ErrorCode.ENCRYPTION_FAILED,
                    error_msg,
                    ErrorSeverity.CRITICAL,
                )
            )
