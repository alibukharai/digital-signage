"""
Security service implementation
"""

import base64
import hashlib
import json
import secrets
import time
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

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

    def encrypt_data(self, data: str, key_id: Optional[str] = None) -> bytes:
        """Encrypt data"""
        try:
            if not self.config.encryption_enabled:
                return data.encode("utf-8")

            # Use session key if provided, otherwise master key
            if key_id and key_id in self.sessions:
                key = self.sessions[key_id].get("encryption_key", self.master_key)
            else:
                key = self.master_key

            fernet = Fernet(key)
            encrypted = fernet.encrypt(data.encode("utf-8"))

            if self.logger:
                self.logger.debug(f"Data encrypted (key_id: {key_id})")

            return encrypted

        except Exception as e:
            if self.logger:
                self.logger.error(f"Encryption failed: {e}")
            raise SecurityError(
                ErrorCode.ENCRYPTION_FAILED,
                f"Failed to encrypt data: {str(e)}",
                ErrorSeverity.HIGH,
            )

    def decrypt_data(self, encrypted_data: bytes, key_id: Optional[str] = None) -> str:
        """Decrypt data"""
        try:
            if not self.config.encryption_enabled:
                return encrypted_data.decode("utf-8")

            # Use session key if provided, otherwise master key
            if key_id and key_id in self.sessions:
                key = self.sessions[key_id].get("encryption_key", self.master_key)
            else:
                key = self.master_key

            fernet = Fernet(key)
            decrypted = fernet.decrypt(encrypted_data)

            if self.logger:
                self.logger.debug(f"Data decrypted (key_id: {key_id})")

            return decrypted.decode("utf-8")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Decryption failed: {e}")
            raise SecurityError(
                ErrorCode.ENCRYPTION_FAILED,
                f"Failed to decrypt data: {str(e)}",
                ErrorSeverity.HIGH,
            )

    def validate_credentials(self, ssid: str, password: str) -> bool:
        """Validate network credentials"""
        try:
            # Basic validation
            if not ssid or not ssid.strip():
                return False

            if not password or len(password) < 8:
                return False

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
                    return False

            # Check for excessive length
            if len(ssid) > 32 or len(password) > 64:
                return False

            # Check for null bytes or control characters
            for char in ssid + password:
                if ord(char) < 32 and char not in ["\t", "\n", "\r"]:
                    return False

            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Credential validation error: {e}")
            return False

    def create_session(self, client_id: str) -> str:
        """Create secure session"""
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

            return session_id

        except Exception as e:
            if self.logger:
                self.logger.error(f"Session creation failed: {e}")
            raise SecurityError(
                ErrorCode.SESSION_EXPIRED,
                f"Failed to create session: {str(e)}",
                ErrorSeverity.MEDIUM,
            )

    def cleanup_expired_sessions(self) -> None:
        """Clean up expired session keys"""
        self._cleanup_expired_sessions()

    def _cleanup_expired_sessions(self):
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
