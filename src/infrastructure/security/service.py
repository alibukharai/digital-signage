"""
Main Security service implementation using refactored modules
"""

import secrets
import time
from typing import Any, Dict, Optional

from ...common.result_handling import Result
from ...domain.configuration import SecurityConfig
from ...domain.errors import ErrorCode, ErrorSeverity, SecurityError
from ...interfaces import ILogger, ISecurityService
from .encryption import EncryptionManager
from .session_manager import SessionManager


class SecurityService(ISecurityService):
    """
    Concrete implementation of security service
    Refactored into smaller, focused modules for better maintainability
    """

    def __init__(self, config: SecurityConfig, logger: Optional[ILogger] = None):
        self.config = config
        self.logger = logger
        
        # Initialize managers
        self.encryption_manager = EncryptionManager(logger)
        self.session_manager = SessionManager(logger)
        
        # Generate master key
        self.master_key = self._generate_master_key()
        
        if self.logger:
            self.logger.info("Security service initialized with modular architecture")

    def encrypt_data(self, data: str, key_id: Optional[str] = None) -> Result[bytes, Exception]:
        """Encrypt data using encryption manager"""
        try:
            # Get the appropriate key
            key = self._get_encryption_key(key_id)
            if not key:
                error_msg = "Unable to obtain encryption key"
                if self.logger:
                    self.logger.error(error_msg)
                return Result.failure(
                    SecurityError(
                        ErrorCode.ENCRYPTION_FAILED,
                        error_msg,
                        ErrorSeverity.CRITICAL,
                    )
                )

            # Auto-rotate key if needed
            if key_id and self._should_rotate_key(key_id):
                self._rotate_session_key_internal(key_id)
                key = self._get_encryption_key(key_id)

            return self.encryption_manager.encrypt_data(data, key)

        except (ValueError, TypeError) as e:
            error_msg = f"Encryption failed: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                SecurityError(
                    ErrorCode.ENCRYPTION_FAILED,
                    error_msg,
                    ErrorSeverity.HIGH,
                )
            )

    def decrypt_data(self, encrypted_data: bytes, key_id: Optional[str] = None) -> Result[str, Exception]:
        """Decrypt data using encryption manager"""
        try:
            # Get the appropriate key
            key = self._get_encryption_key(key_id)
            if not key:
                error_msg = "Unable to obtain decryption key"
                if self.logger:
                    self.logger.error(error_msg)
                return Result.failure(
                    SecurityError(
                        ErrorCode.ENCRYPTION_FAILED,
                        error_msg,
                        ErrorSeverity.CRITICAL,
                    )
                )

            return self.encryption_manager.decrypt_data(encrypted_data, key)

        except (ValueError, TypeError) as e:
            error_msg = f"Decryption failed: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                SecurityError(
                    ErrorCode.ENCRYPTION_FAILED,
                    error_msg,
                    ErrorSeverity.HIGH,
                )
            )

    def create_session(self, session_id: str, user_data: Optional[Dict[str, Any]] = None) -> Result[str, Exception]:
        """Create a new security session"""
        try:
            # Create session
            result = self.session_manager.create_session(session_id, user_data)
            
            if result.is_success():
                # Generate and set encryption key for session
                session_key = self.encryption_manager.generate_key()
                key_result = self.session_manager.rotate_session_key(session_id, session_key)
                
                if key_result.is_failure():
                    # Cleanup session if key setting failed
                    self.session_manager._cleanup_session(session_id)
                    return key_result
                
                if self.logger:
                    self.logger.info(f"Security session created with encryption key: {session_id}")
            
            return result

        except (ValueError, TypeError) as e:
            error_msg = f"Session creation failed: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                SecurityError(
                    ErrorCode.SESSION_EXPIRED,
                    error_msg,
                    ErrorSeverity.HIGH,
                )
            )

    def validate_session(self, session_id: str) -> Result[bool, Exception]:
        """Validate session using session manager"""
        result = self.session_manager.validate_session(session_id)
        
        # Clean up expired sessions periodically
        if result.is_failure():
            self.session_manager.cleanup_expired_sessions()
        
        return result

    def authenticate_session(self, session_id: str, credentials: Dict[str, Any]) -> Result[bool, Exception]:
        """Authenticate session using session manager"""
        return self.session_manager.authenticate_session(session_id, credentials)

    def hash_password(self, password: str, salt: Optional[bytes] = None) -> str:
        """Hash password using encryption manager"""
        return self.encryption_manager.hash_data(password, salt)

    def verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify password using encryption manager"""
        return self.encryption_manager.verify_hash(password, stored_hash)

    def generate_token(self, length: int = 32) -> str:
        """Generate secure random token"""
        try:
            token_bytes = secrets.token_bytes(length)
            return token_bytes.hex()

        except (ValueError, TypeError) as e:
            if self.logger:
                self.logger.error(f"Token generation failed: {str(e)}")
            raise SecurityError(
                ErrorCode.ENCRYPTION_FAILED,
                "Failed to generate secure token",
                ErrorSeverity.HIGH,
            )

    def detect_plaintext_credentials(self, data: str) -> bool:
        """Detect plaintext credentials using encryption manager"""
        return self.encryption_manager._detect_plaintext_credentials(data)

    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        return self.session_manager.cleanup_expired_sessions()

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information"""
        return self.session_manager.get_session_info(session_id)

    def _generate_master_key(self) -> bytes:
        """Generate master encryption key"""
        try:
            # Use encryption manager to generate master key
            master_key = self.encryption_manager.generate_key()
            
            if self.logger:
                self.logger.debug("Master encryption key generated")
            
            return master_key

        except Exception as e:
            if self.logger:
                self.logger.error(f"Master key generation failed: {str(e)}")
            raise SecurityError(
                ErrorCode.ENCRYPTION_FAILED,
                "Failed to generate master encryption key",
                ErrorSeverity.CRITICAL,
            )

    def _get_encryption_key(self, key_id: Optional[str] = None) -> Optional[bytes]:
        """Get encryption key for session or master key"""
        try:
            if key_id:
                session_info = self.session_manager.get_session_info(key_id)
                if session_info:
                    # Get session key from session manager's internal data
                    with self.session_manager._session_lock:
                        if key_id in self.session_manager.sessions:
                            return self.session_manager.sessions[key_id].get("encryption_key")
            
            # Fall back to master key
            return self.master_key

        except (KeyError, TypeError):
            return self.master_key

    def _should_rotate_key(self, key_id: str) -> bool:
        """Check if session key should be rotated"""
        try:
            with self.session_manager._session_lock:
                if key_id not in self.session_manager.sessions:
                    return False
                
                session_data = self.session_manager.sessions[key_id]
                key_age = time.time() - session_data.get("key_created", 0)
                
                # Rotate keys older than 1 hour
                return key_age > 3600

        except (KeyError, TypeError):
            return False

    def _rotate_session_key_internal(self, key_id: str) -> None:
        """Internal method to rotate session key"""
        try:
            new_key = self.encryption_manager.generate_key()
            result = self.session_manager.rotate_session_key(key_id, new_key)
            
            if result.is_success() and self.logger:
                self.logger.debug(f"Session key rotated for {key_id}")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Key rotation failed for {key_id}: {str(e)}")

    def _detect_key_compromise(self, key: bytes) -> bool:
        """Detect key compromise using encryption manager"""
        return self.encryption_manager._detect_key_compromise(key)