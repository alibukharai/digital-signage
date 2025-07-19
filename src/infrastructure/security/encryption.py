"""
Encryption and cryptographic operations
"""

import base64
import hashlib
import secrets
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ...common.result_handling import Result
from ...domain.errors import ErrorCode, ErrorSeverity, SecurityError
from ...interfaces import ILogger


class EncryptionManager:
    """Handles all encryption and cryptographic operations"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger

    def encrypt_data(self, data: str, key: bytes) -> Result[bytes, Exception]:
        """Encrypt data using Fernet encryption"""
        try:
            # Validate input data for security threats
            if self._detect_plaintext_credentials(data):
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

            # Validate encryption key
            if not key or len(key) < 32:
                error_msg = "Invalid or missing encryption key"
                if self.logger:
                    self.logger.error(error_msg)
                return Result.failure(
                    SecurityError(
                        ErrorCode.ENCRYPTION_FAILED,
                        error_msg,
                        ErrorSeverity.CRITICAL,
                    )
                )

            # Check for key compromise
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

            if self.logger:
                self.logger.debug("Data encrypted successfully")

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

    def decrypt_data(self, encrypted_data: bytes, key: bytes) -> Result[str, Exception]:
        """Decrypt data using Fernet decryption"""
        try:
            # Validate inputs
            if not encrypted_data:
                error_msg = "No encrypted data provided"
                if self.logger:
                    self.logger.error(error_msg)
                return Result.failure(
                    SecurityError(
                        ErrorCode.ENCRYPTION_FAILED,
                        error_msg,
                        ErrorSeverity.MEDIUM,
                    )
                )

            if not key or len(key) < 32:
                error_msg = "Invalid decryption key"
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
            result = decrypted.decode("utf-8")

            if self.logger:
                self.logger.debug("Data decrypted successfully")

            return Result.success(result)

        except ValueError as e:
            error_msg = "Invalid encrypted data format"
            if self.logger:
                self.logger.error(f"Decryption failed: Invalid format - {str(e)}")
            return Result.failure(
                SecurityError(
                    ErrorCode.ENCRYPTION_FAILED,
                    error_msg,
                    ErrorSeverity.HIGH,
                )
            )
        except TypeError as e:
            error_msg = "Invalid data type for decryption"
            if self.logger:
                self.logger.error(f"Decryption failed: Invalid type - {str(e)}")
            return Result.failure(
                SecurityError(
                    ErrorCode.ENCRYPTION_FAILED,
                    error_msg,
                    ErrorSeverity.HIGH,
                )
            )

    def generate_key(self, password: Optional[str] = None, salt: Optional[bytes] = None) -> bytes:
        """Generate encryption key from password or create random key"""
        try:
            if password:
                # Generate key from password using PBKDF2
                if not salt:
                    salt = secrets.token_bytes(32)
                
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            else:
                # Generate random key
                key = Fernet.generate_key()

            if self.logger:
                self.logger.debug("Encryption key generated successfully")

            return key

        except (ValueError, TypeError) as e:
            if self.logger:
                self.logger.error(f"Key generation failed: {str(e)}")
            raise SecurityError(
                ErrorCode.ENCRYPTION_FAILED,
                "Failed to generate encryption key",
                ErrorSeverity.CRITICAL,
            )

    def hash_data(self, data: str, salt: Optional[bytes] = None) -> str:
        """Create cryptographic hash of data"""
        try:
            if not salt:
                salt = secrets.token_bytes(32)
            
            # Use SHA-256 for hashing
            hasher = hashlib.sha256()
            hasher.update(salt + data.encode('utf-8'))
            hash_bytes = hasher.digest()
            
            # Combine salt and hash for storage
            combined = salt + hash_bytes
            return base64.b64encode(combined).decode('utf-8')

        except (ValueError, TypeError) as e:
            if self.logger:
                self.logger.error(f"Hashing failed: {str(e)}")
            raise SecurityError(
                ErrorCode.ENCRYPTION_FAILED,
                "Failed to hash data",
                ErrorSeverity.HIGH,
            )

    def verify_hash(self, data: str, stored_hash: str) -> bool:
        """Verify data against stored hash"""
        try:
            # Decode the stored hash
            combined = base64.b64decode(stored_hash.encode('utf-8'))
            salt = combined[:32]
            stored_hash_bytes = combined[32:]
            
            # Hash the input data with the same salt
            hasher = hashlib.sha256()
            hasher.update(salt + data.encode('utf-8'))
            input_hash = hasher.digest()
            
            # Compare hashes
            return secrets.compare_digest(stored_hash_bytes, input_hash)

        except (ValueError, TypeError) as e:
            if self.logger:
                self.logger.error(f"Hash verification failed: {str(e)}")
            return False

    def _detect_plaintext_credentials(self, data: str) -> bool:
        """Detect if data contains plaintext credentials"""
        try:
            # Check for common credential patterns
            suspicious_patterns = [
                "password=",
                "pwd=",
                "secret=",
                "token=",
                "key=",
                "auth=",
                "credential",
            ]
            
            data_lower = data.lower()
            for pattern in suspicious_patterns:
                if pattern in data_lower:
                    return True
                    
            return False

        except (AttributeError, TypeError):
            return False

    def _detect_key_compromise(self, key: bytes) -> bool:
        """Detect potential key compromise"""
        try:
            # Check key length
            if len(key) < 32:
                return True
                
            # Check for all zeros or all ones
            if key == b'\x00' * len(key) or key == b'\xFF' * len(key):
                return True
                
            # Check for common weak keys (simplified check)
            weak_patterns = [b'1234', b'0000', b'aaaa', b'ffff']
            for pattern in weak_patterns:
                if pattern in key:
                    return True
                    
            return False

        except (AttributeError, TypeError):
            return True  # Assume compromised if we can't verify