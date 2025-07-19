"""
Security service implementation with consistent error handling using Result pattern
"""

import base64
import hashlib
import json
import os
import platform
import secrets
import threading
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

        # Add session management locks and security enhancements
        self._session_lock = threading.Lock()
        self._key_rotation_lock = threading.Lock()
        self._failed_attempts: Dict[str, int] = {}  # Track failed attempts per session
        self._session_cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()

        if self.logger:
            self.logger.info(
                "Security service initialized with enhanced session management"
            )

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

        except ValueError as e:
            error_msg = "Invalid input data for encryption"
            if self.logger:
                self.logger.error(f"Encryption failed: Invalid input data format - {str(e)}")
            return Result.failure(
                SecurityError(
                    ErrorCode.ENCRYPTION_FAILED,
                    error_msg,
                    ErrorSeverity.CRITICAL,
                )
            )
        except TypeError as e:
            error_msg = "Invalid data type for encryption"
            if self.logger:
                self.logger.error(f"Encryption failed: Invalid data type - {str(e)}")
            return Result.failure(
                SecurityError(
                    ErrorCode.ENCRYPTION_FAILED,
                    error_msg,
                    ErrorSeverity.CRITICAL,
                )
            )
        except MemoryError:
            error_msg = "Insufficient memory for encryption operation"
            if self.logger:
                self.logger.error("Encryption failed: Insufficient memory")
            return Result.failure(
                SecurityError(
                    ErrorCode.ENCRYPTION_FAILED,
                    error_msg,
                    ErrorSeverity.CRITICAL,
                )
            )
        except OSError as e:
            error_msg = "System error during encryption"
            if self.logger:
                self.logger.error(f"Encryption failed: System error - {str(e)}")
            return Result.failure(
                SecurityError(
                    ErrorCode.ENCRYPTION_FAILED,
                    error_msg,
                    ErrorSeverity.HIGH,
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
            # Enhanced error handling for decryption operations
            error_msg = f"Failed to decrypt data: {str(e)}"

            # Log security-relevant errors without exposing sensitive data
            if self.logger:
                error_type = type(e).__name__
                self.logger.error(
                    f"Decryption failed - Error type: {error_type}, Key ID: {key_id or 'master'}"
                )

                # Log additional context for debugging
                if "InvalidToken" in error_type:
                    self.logger.error(
                        "Decryption failed: Invalid token or corrupted data"
                    )
                elif "ValueError" in error_type:
                    self.logger.error(
                        "Decryption failed: Invalid encrypted data format"
                    )
                else:
                    self.logger.error(
                        f"Decryption failed: Unexpected error - {error_type}"
                    )

            # Track failed decryption attempts for session security
            if key_id and key_id in self.sessions:
                with self._session_lock:
                    self._failed_attempts[key_id] = (
                        self._failed_attempts.get(key_id, 0) + 1
                    )
                    if self._failed_attempts[key_id] > 3:
                        if self.logger:
                            self.logger.warning(
                                f"Multiple decryption failures for session {key_id}, terminating session"
                            )
                        # Terminate session after multiple failures
                        del self.sessions[key_id]
                        del self._failed_attempts[key_id]

            # Don't return raw exception details to avoid information leakage
            return Result.failure(
                SecurityError(
                    ErrorCode.ENCRYPTION_FAILED,
                    "Decryption operation failed - check logs for details",
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
        """Internal method to cleanup expired sessions with enhanced security"""
        try:
            current_time = time.time()
            expired_sessions = []

            # Identify expired sessions
            for session_id, session_data in self.sessions.items():
                last_activity = session_data.get("last_activity", 0)
                if current_time - last_activity > self.config.session_timeout:
                    expired_sessions.append(session_id)

            # Remove expired sessions and their tracking data
            for session_id in expired_sessions:
                if session_id in self.sessions:
                    del self.sessions[session_id]

                # Clean up failed attempts tracking
                self._failed_attempts.pop(session_id, None)

                if self.logger:
                    self.logger.debug(
                        f"Session expired and cleaned up: {session_id[:8]}..."
                    )

            if expired_sessions and self.logger:
                self.logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

            # Also clean up orphaned failed attempt records
            orphaned_failures = []
            for session_id in self._failed_attempts:
                if session_id not in self.sessions:
                    orphaned_failures.append(session_id)

            for session_id in orphaned_failures:
                del self._failed_attempts[session_id]

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
        """Validate session with enhanced security checks"""
        with self._session_lock:
            try:
                if session_id not in self.sessions:
                    if self.logger:
                        self.logger.warning(
                            f"Session validation failed: unknown session {session_id[:8]}..."
                        )
                    return False

                session_data = self.sessions[session_id]
                current_time = time.time()

                # Check if session expired
                last_activity = session_data.get("last_activity", 0)
                if current_time - last_activity > self.config.session_timeout:
                    if self.logger:
                        self.logger.info(f"Session expired: {session_id[:8]}...")
                    del self.sessions[session_id]
                    # Clean up failed attempts tracking
                    self._failed_attempts.pop(session_id, None)
                    return False

                # Check for suspicious activity (too many failed attempts)
                failed_count = self._failed_attempts.get(session_id, 0)
                if failed_count > 5:
                    if self.logger:
                        self.logger.warning(
                            f"Session blocked due to excessive failures: {session_id[:8]}..."
                        )
                    del self.sessions[session_id]
                    del self._failed_attempts[session_id]
                    return False

                # Update last activity
                session_data["last_activity"] = current_time

                # Periodic cleanup of expired sessions
                if current_time - self._last_cleanup > self._session_cleanup_interval:
                    self._cleanup_expired_sessions()
                    self._last_cleanup = current_time

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
            # Early return for empty or very short data
            if not data or len(data.strip()) < 5:
                return False

            # Check if data looks like JSON credentials
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    # Check for credential fields in JSON
                    credential_fields = {
                        "ssid",
                        "password",
                        "passphrase",
                        "psk",
                        "key",
                        "secret",
                        "token",
                        "auth",
                        "credential",
                        "username",
                        "user",
                        "pass",
                        "pwd",
                        "api_key",
                        "private_key",
                        "wifi_password",
                        "network_key",
                    }

                    found_fields = set(key.lower() for key in parsed.keys())
                    if found_fields.intersection(credential_fields):
                        if self.logger:
                            self.logger.warning(
                                f"Plaintext JSON credentials detected with fields: {found_fields.intersection(credential_fields)}"
                            )
                        return True

                    # Check for nested credential objects
                    for value in parsed.values():
                        if isinstance(value, dict):
                            nested_fields = set(key.lower() for key in value.keys())
                            if nested_fields.intersection(credential_fields):
                                if self.logger:
                                    self.logger.warning(
                                        "Plaintext nested credentials detected"
                                    )
                                return True

            except json.JSONDecodeError:
                pass

            # Check for common plaintext patterns with enhanced detection
            plaintext_indicators = [
                '"ssid":',
                '"password":',
                '"passphrase":',
                '"psk":',
                '"key":',
                '"secret":',
                '"token":',
                '"auth":',
                '"credential":',
                "wifi_credentials",
                "network_name",
                "network_password",
                "wifi_password=",
                "auth_token=",
                "api_key=",
                "ssid=",
                "password=",
                "username:",
                "password:",
                "user:",
                "pass:",
                "SSID:",
                "PASSWORD:",
                "SECRET:",
                "TOKEN:",
                # Key-value pair patterns
                r"ssid\s*=",
                r"password\s*=",
                r"key\s*=",
                r"secret\s*=",
                # XML/config patterns
                "<password>",
                "<secret>",
                "<key>",
                "<credential>",
                # YAML patterns
                "password:\s",
                "secret:\s",
                "key:\s",
                # Environment variable patterns
                "PASSWORD=",
                "SECRET=",
                "API_KEY=",
                "TOKEN=",
            ]

            data_lower = data.lower()
            for indicator in plaintext_indicators:
                if indicator.lower() in data_lower:
                    if self.logger:
                        self.logger.warning(
                            f"Plaintext indicator detected: {indicator}"
                        )
                    return True

            # Enhanced pattern matching using regex for complex patterns
            import re

            # Patterns that look like credential assignments
            credential_assignment_patterns = [
                r'(password|secret|key|token|auth)\s*[:=]\s*["\']?[^"\'\s]+["\']?',
                r'(ssid|network)\s*[:=]\s*["\']?[^"\'\s]+["\']?',
                r"(wifi|wlan)_?(password|key|secret)\s*[:=]",
                r"api_?key\s*[:=]",
                r"access_?token\s*[:=]",
                r"bearer\s+[A-Za-z0-9_\-\.]+",
            ]

            for pattern in credential_assignment_patterns:
                if re.search(pattern, data_lower, re.IGNORECASE):
                    if self.logger:
                        self.logger.warning(
                            f"Credential assignment pattern detected: {pattern}"
                        )
                    return True

            # Check for URL-encoded credentials
            try:
                import urllib.parse

                decoded_url = urllib.parse.unquote(data)
                if decoded_url != data and self.detect_plaintext_credentials(
                    decoded_url
                ):
                    if self.logger:
                        self.logger.warning(
                            "URL-encoded plaintext credentials detected"
                        )
                    return True
            except Exception:
                pass

            # Check for suspicious combination of networking terms and secrets
            networking_terms = ["wifi", "wlan", "network", "ssid", "access", "point"]
            secret_terms = ["password", "pass", "secret", "key", "token", "auth"]

            has_networking = any(term in data_lower for term in networking_terms)
            has_secret = any(term in data_lower for term in secret_terms)

            if has_networking and has_secret:
                # Additional validation - check if it looks like structured data
                if ":" in data or "=" in data or "{" in data or "[" in data:
                    if self.logger:
                        self.logger.warning(
                            "Suspected plaintext network credentials based on content analysis"
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
        """Detect potential key compromise indicators with enhanced analysis"""
        try:
            # Check for all-zero key
            if key == b"\x00" * len(key):
                if self.logger:
                    self.logger.error("Key compromise detected: all-zero key")
                return True

            # Check for all-one key
            if key == b"\xFF" * len(key):
                if self.logger:
                    self.logger.error("Key compromise detected: all-one key")
                return True

            # Check for suspiciously short keys
            if len(key) < 32:
                if self.logger:
                    self.logger.error(
                        f"Key compromise detected: key too short ({len(key)} bytes)"
                    )
                return True

            # Check for known weak patterns (enhanced)
            weak_patterns = [
                b"AAAAAAAA",
                b"BBBBBBBB",
                b"CCCCCCCC",
                b"\x01\x02\x03\x04",
                b"\x04\x03\x02\x01",
                b"\xFF" * 8,
                b"\x00" * 8,
                b"12345678",
                b"87654321",
                b"abcdefgh",
                b"ABCDEFGH",
                b"password",
                b"PASSWORD",
                b"secret12",
                b"key12345",
            ]

            for pattern in weak_patterns:
                if pattern in key:
                    if self.logger:
                        self.logger.error(
                            f"Key compromise detected: weak pattern found"
                        )
                    return True

            # Check for insufficient entropy (repeated bytes)
            unique_bytes = len(set(key))
            entropy_ratio = unique_bytes / len(key)

            if entropy_ratio < 0.25:  # Less than 25% unique bytes
                if self.logger:
                    self.logger.error(
                        f"Key compromise detected: low entropy (ratio: {entropy_ratio:.2f})"
                    )
                return True

            # Check for sequential patterns
            sequential_count = 0
            for i in range(len(key) - 1):
                if abs(key[i] - key[i + 1]) == 1:
                    sequential_count += 1

            if sequential_count > len(key) * 0.5:  # More than 50% sequential
                if self.logger:
                    self.logger.error(
                        "Key compromise detected: too many sequential bytes"
                    )
                return True

            # Check for repeated patterns longer than 4 bytes
            for pattern_len in range(4, min(16, len(key) // 2)):
                pattern = key[:pattern_len]
                pattern_count = 0
                for i in range(0, len(key) - pattern_len + 1, pattern_len):
                    if key[i : i + pattern_len] == pattern:
                        pattern_count += 1

                if pattern_count > 2:  # Pattern repeats more than twice
                    if self.logger:
                        self.logger.error(
                            f"Key compromise detected: repeating pattern of length {pattern_len}"
                        )
                    return True

            # Check for known test/default keys (should be configurable in production)
            known_weak_keys = [
                # Common test keys (base64 encoded Fernet keys)
                b"ZmDfcTF7_60GrrY167zsiPd67pEvs0aQqHrIwJzROF0=",
                b"your-secret-key-here" + b"\x00" * 8,  # Padded default
                b"test-key-do-not-use-in-prod",
                b"development-key-only",
            ]

            for weak_key in known_weak_keys:
                if key.startswith(weak_key[: min(len(weak_key), len(key))]):
                    if self.logger:
                        self.logger.error(
                            "Key compromise detected: known weak/test key"
                        )
                    return True

            # Advanced: Check for keys that might be derived from predictable sources
            # (This is a simplified check - in production, you might want more sophisticated analysis)
            try:
                # Check if key looks like it could be a hash of common words
                import hashlib

                common_sources = [
                    b"password123",
                    b"secret",
                    b"default",
                    b"admin",
                    b"test",
                    b"development",
                    b"production",
                    b"rockpi",
                    b"provisioning",
                ]

                for source in common_sources:
                    for salt in [b"", b"salt", b"rockpi3399", b"provisioning"]:
                        test_key = hashlib.sha256(source + salt).digest()
                        if key.startswith(test_key[: min(len(test_key), len(key))]):
                            if self.logger:
                                self.logger.error(
                                    "Key compromise detected: predictable key derivation"
                                )
                            return True

            except Exception:
                # If analysis fails, don't flag as compromise
                pass

            return False

        except Exception as e:
            if self.logger:
                self.logger.error(f"Key compromise analysis failed: {e}")
            # If we can't analyze the key, assume compromise for safety
            return True

    def _rotate_session_key_internal(self, session_id: str) -> bool:
        """Internally rotate session encryption key with proper locking"""
        with self._key_rotation_lock:
            try:
                if session_id not in self.sessions:
                    return False

                # Generate new session key
                new_key = Fernet.generate_key()

                # Update session with new key
                session_data = self.sessions[session_id]
                old_key_created = session_data.get("key_created", 0)

                session_data["encryption_key"] = new_key
                session_data["key_created"] = time.time()
                session_data["previous_key_created"] = old_key_created

                if self.logger:
                    self.logger.info(
                        f"Session key rotated for session {session_id[:8]}..."
                    )

                return True

            except Exception as e:
                if self.logger:
                    self.logger.error(
                        f"Key rotation failed for session {session_id[:8]}...: {e}"
                    )
                return False

    def force_session_cleanup(self) -> int:
        """Force cleanup of all sessions - useful for security incidents"""
        with self._session_lock:
            try:
                session_count = len(self.sessions)
                self.sessions.clear()
                self._failed_attempts.clear()

                if self.logger:
                    self.logger.warning(
                        f"Force cleanup performed - {session_count} sessions terminated"
                    )

                return session_count

            except Exception as e:
                if self.logger:
                    self.logger.error(f"Force cleanup failed: {e}")
                return 0

    def _enforce_encryption_compliance(self, data: str) -> Result[bool, Exception]:
        """Enforce encryption compliance - reject any unencrypted sensitive data"""
        try:
            # Check if the data contains sensitive patterns that must be encrypted
            if self.detect_plaintext_credentials(data):
                error_msg = (
                    "Encryption compliance violation: sensitive data must be encrypted"
                )
                if self.logger:
                    self.logger.error(error_msg)
                return Result.failure(
                    SecurityError(
                        ErrorCode.ENCRYPTION_FAILED,
                        error_msg,
                        ErrorSeverity.CRITICAL,
                    )
                )

            # Enhanced pattern detection for various credential formats
            sensitive_patterns = [
                "password:",
                "passphrase:",
                "secret:",
                "key:",
                "token:",
                "auth:",
                "credential",
                "wifi_password=",
                "auth_token=",
                "api_key=",
                "private_key",
                "certificate",
                "bearer ",
                "authorization:",
            ]

            data_lower = data.lower()
            for pattern in sensitive_patterns:
                if pattern in data_lower:
                    error_msg = f"Encryption compliance violation: detected sensitive pattern '{pattern}'"
                    if self.logger:
                        self.logger.warning(error_msg)
                    return Result.failure(
                        SecurityError(
                            ErrorCode.ENCRYPTION_FAILED,
                            error_msg,
                            ErrorSeverity.HIGH,
                        )
                    )

            # Check for structured credential data (even without obvious keywords)
            try:
                parsed_data = json.loads(data)
                if isinstance(parsed_data, dict):
                    # Check for credential-like structures
                    suspicious_keys = {
                        "ssid",
                        "password",
                        "passphrase",
                        "psk",
                        "key",
                        "secret",
                        "token",
                        "auth",
                        "credential",
                        "username",
                        "user",
                        "pass",
                        "pwd",
                        "api_key",
                        "private_key",
                        "cert",
                        "certificate",
                    }

                    found_keys = set(key.lower() for key in parsed_data.keys())
                    if found_keys.intersection(suspicious_keys):
                        error_msg = "Encryption compliance violation: structured credential data detected"
                        if self.logger:
                            self.logger.error(error_msg)
                        return Result.failure(
                            SecurityError(
                                ErrorCode.ENCRYPTION_FAILED,
                                error_msg,
                                ErrorSeverity.CRITICAL,
                            )
                        )
            except json.JSONDecodeError:
                # Not JSON, continue with other checks
                pass

            # Check for base64-encoded data that might contain credentials
            try:
                if len(data) > 20 and "=" in data[-4:]:  # Possible base64 padding
                    import base64

                    decoded = base64.b64decode(data.encode()).decode(
                        "utf-8", errors="ignore"
                    )
                    if self.detect_plaintext_credentials(decoded):
                        error_msg = "Encryption compliance violation: base64-encoded credentials detected"
                        if self.logger:
                            self.logger.warning(error_msg)
                        return Result.failure(
                            SecurityError(
                                ErrorCode.ENCRYPTION_FAILED,
                                error_msg,
                                ErrorSeverity.HIGH,
                            )
                        )
            except Exception:
                # If base64 decoding fails, continue
                pass

            return Result.success(True)

        except Exception as e:
            error_msg = f"Encryption compliance check failed: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                SecurityError(
                    ErrorCode.ENCRYPTION_FAILED,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )
