"""
Session management and authentication
"""

import threading
import time
from typing import Any, Dict, Optional, Set

from ...common.result_handling import Result
from ...domain.errors import ErrorCode, ErrorSeverity, SecurityError
from ...interfaces import ILogger


class SessionManager:
    """Manages security sessions and authentication"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._session_lock = threading.Lock()
        self._key_rotation_lock = threading.Lock()
        self._failed_attempts: Dict[str, int] = {}
        self._session_cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
        self._blocked_sessions: Set[str] = set()

    def create_session(self, session_id: str, user_data: Optional[Dict[str, Any]] = None) -> Result[str, Exception]:
        """Create a new security session"""
        try:
            with self._session_lock:
                if session_id in self.sessions:
                    error_msg = f"Session {session_id} already exists"
                    if self.logger:
                        self.logger.warning(error_msg)
                    return Result.failure(
                        SecurityError(
                            ErrorCode.SESSION_EXPIRED,
                            error_msg,
                            ErrorSeverity.MEDIUM,
                        )
                    )

                # Create session data
                session_data = {
                    "session_id": session_id,
                    "created_at": time.time(),
                    "last_activity": time.time(),
                    "key_created": time.time(),
                    "encryption_key": None,  # Will be set separately
                    "user_data": user_data or {},
                    "authenticated": False,
                    "auth_attempts": 0,
                }

                self.sessions[session_id] = session_data
                self._failed_attempts[session_id] = 0

                if self.logger:
                    self.logger.info(f"Security session created: {session_id}")

                return Result.success(session_id)

        except (ValueError, TypeError) as e:
            error_msg = f"Failed to create session: {str(e)}"
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
        """Validate if session exists and is active"""
        try:
            with self._session_lock:
                # Check if session is blocked
                if session_id in self._blocked_sessions:
                    error_msg = f"Session {session_id} is blocked"
                    if self.logger:
                        self.logger.warning(error_msg)
                    return Result.failure(
                        SecurityError(
                            ErrorCode.UNAUTHORIZED_ACCESS,
                            error_msg,
                            ErrorSeverity.HIGH,
                        )
                    )

                # Check if session exists
                if session_id not in self.sessions:
                    error_msg = f"Session {session_id} not found"
                    if self.logger:
                        self.logger.warning(error_msg)
                    return Result.failure(
                        SecurityError(
                            ErrorCode.SESSION_EXPIRED,
                            error_msg,
                            ErrorSeverity.MEDIUM,
                        )
                    )

                session_data = self.sessions[session_id]
                current_time = time.time()

                # Check session timeout (1 hour default)
                session_timeout = 3600  # 1 hour
                if current_time - session_data["last_activity"] > session_timeout:
                    self._cleanup_session(session_id)
                    error_msg = f"Session {session_id} expired"
                    if self.logger:
                        self.logger.info(error_msg)
                    return Result.failure(
                        SecurityError(
                            ErrorCode.SESSION_EXPIRED,
                            error_msg,
                            ErrorSeverity.LOW,
                        )
                    )

                # Update last activity
                session_data["last_activity"] = current_time

                if self.logger:
                    self.logger.debug(f"Session {session_id} validated successfully")

                return Result.success(True)

        except (KeyError, TypeError) as e:
            error_msg = f"Session validation failed: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                SecurityError(
                    ErrorCode.SESSION_EXPIRED,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

    def authenticate_session(self, session_id: str, credentials: Dict[str, Any]) -> Result[bool, Exception]:
        """Authenticate a session with credentials"""
        try:
            with self._session_lock:
                if session_id not in self.sessions:
                    error_msg = f"Session {session_id} not found for authentication"
                    if self.logger:
                        self.logger.warning(error_msg)
                    return Result.failure(
                        SecurityError(
                            ErrorCode.AUTHENTICATION_FAILED,
                            error_msg,
                            ErrorSeverity.HIGH,
                        )
                    )

                session_data = self.sessions[session_id]
                session_data["auth_attempts"] += 1

                # Check for too many failed attempts
                max_attempts = 3
                if session_data["auth_attempts"] > max_attempts:
                    self._block_session(session_id)
                    error_msg = f"Too many authentication attempts for session {session_id}"
                    if self.logger:
                        self.logger.warning(error_msg)
                    return Result.failure(
                        SecurityError(
                            ErrorCode.UNAUTHORIZED_ACCESS,
                            error_msg,
                            ErrorSeverity.HIGH,
                        )
                    )

                # Validate credentials (simplified validation)
                if self._validate_credentials(credentials):
                    session_data["authenticated"] = True
                    session_data["auth_attempts"] = 0  # Reset on success
                    session_data["last_activity"] = time.time()

                    if self.logger:
                        self.logger.info(f"Session {session_id} authenticated successfully")

                    return Result.success(True)
                else:
                    error_msg = "Invalid credentials"
                    if self.logger:
                        self.logger.warning(f"Authentication failed for session {session_id}")
                    return Result.failure(
                        SecurityError(
                            ErrorCode.AUTHENTICATION_FAILED,
                            error_msg,
                            ErrorSeverity.MEDIUM,
                        )
                    )

        except (KeyError, TypeError, ValueError) as e:
            error_msg = f"Authentication failed: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                SecurityError(
                    ErrorCode.AUTHENTICATION_FAILED,
                    error_msg,
                    ErrorSeverity.HIGH,
                )
            )

    def rotate_session_key(self, session_id: str, new_key: bytes) -> Result[bool, Exception]:
        """Rotate encryption key for a session"""
        try:
            with self._key_rotation_lock:
                if session_id not in self.sessions:
                    error_msg = f"Session {session_id} not found for key rotation"
                    if self.logger:
                        self.logger.warning(error_msg)
                    return Result.failure(
                        SecurityError(
                            ErrorCode.SESSION_EXPIRED,
                            error_msg,
                            ErrorSeverity.MEDIUM,
                        )
                    )

                # Validate new key
                if not new_key or len(new_key) < 32:
                    error_msg = "Invalid encryption key for rotation"
                    if self.logger:
                        self.logger.error(error_msg)
                    return Result.failure(
                        SecurityError(
                            ErrorCode.ENCRYPTION_FAILED,
                            error_msg,
                            ErrorSeverity.HIGH,
                        )
                    )

                session_data = self.sessions[session_id]
                session_data["encryption_key"] = new_key
                session_data["key_created"] = time.time()
                session_data["last_activity"] = time.time()

                if self.logger:
                    self.logger.info(f"Encryption key rotated for session {session_id}")

                return Result.success(True)

        except (KeyError, TypeError) as e:
            error_msg = f"Key rotation failed: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                SecurityError(
                    ErrorCode.ENCRYPTION_FAILED,
                    error_msg,
                    ErrorSeverity.HIGH,
                )
            )

    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions and return count of cleaned sessions"""
        try:
            current_time = time.time()
            
            # Only cleanup if enough time has passed
            if current_time - self._last_cleanup < self._session_cleanup_interval:
                return 0

            with self._session_lock:
                expired_sessions = []
                session_timeout = 3600  # 1 hour

                for session_id, session_data in self.sessions.items():
                    if current_time - session_data["last_activity"] > session_timeout:
                        expired_sessions.append(session_id)

                # Remove expired sessions
                for session_id in expired_sessions:
                    self._cleanup_session(session_id)

                self._last_cleanup = current_time

                if self.logger and expired_sessions:
                    self.logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

                return len(expired_sessions)

        except (KeyError, TypeError) as e:
            if self.logger:
                self.logger.error(f"Session cleanup failed: {str(e)}")
            return 0

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information (without sensitive data)"""
        try:
            with self._session_lock:
                if session_id not in self.sessions:
                    return None

                session_data = self.sessions[session_id]
                
                # Return safe session info
                return {
                    "session_id": session_data["session_id"],
                    "created_at": session_data["created_at"],
                    "last_activity": session_data["last_activity"],
                    "authenticated": session_data["authenticated"],
                    "auth_attempts": session_data["auth_attempts"],
                }

        except (KeyError, TypeError):
            return None

    def _cleanup_session(self, session_id: str) -> None:
        """Internal method to cleanup a specific session"""
        try:
            if session_id in self.sessions:
                del self.sessions[session_id]
            if session_id in self._failed_attempts:
                del self._failed_attempts[session_id]
            if session_id in self._blocked_sessions:
                self._blocked_sessions.remove(session_id)

        except (KeyError, TypeError):
            pass

    def _block_session(self, session_id: str) -> None:
        """Block a session due to security violations"""
        try:
            self._blocked_sessions.add(session_id)
            if self.logger:
                self.logger.warning(f"Session {session_id} blocked due to security violations")

        except (TypeError, AttributeError):
            pass

    def _validate_credentials(self, credentials: Dict[str, Any]) -> bool:
        """Validate authentication credentials (simplified implementation)"""
        try:
            # This is a simplified validation
            # In production, this would integrate with proper authentication systems
            
            required_fields = ["username", "password"]
            for field in required_fields:
                if field not in credentials or not credentials[field]:
                    return False

            # Basic validation (in production, use proper password hashing)
            username = credentials.get("username", "")
            password = credentials.get("password", "")
            
            # Check minimum requirements
            if len(username) < 3 or len(password) < 6:
                return False

            # Additional validation logic would go here
            return True

        except (KeyError, TypeError, AttributeError):
            return False