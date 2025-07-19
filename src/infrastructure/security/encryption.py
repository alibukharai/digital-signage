"""
Encryption and cryptographic operations with enhanced security
"""

import base64
import hashlib
import mmap
import os
import secrets
import sys
from typing import Optional, Union
import gc

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from ...common.result_handling import Result
from ...domain.errors import ErrorCode, ErrorSeverity, SecurityError
from ...interfaces import ILogger


class SecureMemory:
    """Secure memory handling for sensitive data"""
    
    def __init__(self, data: Union[str, bytes]):
        if isinstance(data, str):
            data = data.encode('utf-8')
        self._size = len(data)
        # Use mmap for secure memory allocation when possible
        try:
            self._memory = mmap.mmap(-1, self._size)
            self._memory.write(data)
            self._memory.seek(0)
        except OSError:
            # Fallback to bytearray if mmap fails
            self._memory = bytearray(data)
    
    def get_data(self) -> bytes:
        """Get data from secure memory"""
        if hasattr(self._memory, 'read'):
            self._memory.seek(0)
            return self._memory.read()
        return bytes(self._memory)
    
    def clear(self):
        """Securely clear memory"""
        try:
            if hasattr(self._memory, 'write'):
                self._memory.seek(0)
                self._memory.write(b'\x00' * self._size)
            else:
                for i in range(len(self._memory)):
                    self._memory[i] = 0
        except Exception:
            pass
        finally:
            if hasattr(self._memory, 'close'):
                self._memory.close()
            # Force garbage collection
            gc.collect()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.clear()


class EncryptionManager:
    """Handles all encryption and cryptographic operations with enhanced security"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        # Use ChaCha20-Poly1305 for better security than Fernet
        self._cipher = ChaCha20Poly1305(ChaCha20Poly1305.generate_key())

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
        """Enhanced detection of plaintext credentials using multiple methods"""
        try:
            if not data or not isinstance(data, str):
                return False
                
            data_lower = data.lower()
            
            # Enhanced pattern matching with more comprehensive patterns
            credential_patterns = [
                # Direct credential indicators
                r"password\s*[:=]\s*['\"]?[^'\">\s]{3,}",
                r"passwd\s*[:=]\s*['\"]?[^'\">\s]{3,}",
                r"pwd\s*[:=]\s*['\"]?[^'\">\s]{3,}",
                r"secret\s*[:=]\s*['\"]?[^'\">\s]{8,}",
                r"token\s*[:=]\s*['\"]?[^'\">\s]{8,}",
                r"api_?key\s*[:=]\s*['\"]?[^'\">\s]{8,}",
                r"private_?key\s*[:=]",
                r"auth\w*\s*[:=]\s*['\"]?[^'\">\s]{8,}",
                
                # Common credential formats
                r"[a-zA-Z0-9+/]{20,}={0,2}",  # Base64-like patterns
                r"[0-9a-fA-F]{32,}",  # Hex patterns (hashes, keys)
                r"-----BEGIN\s+(PRIVATE\s+KEY|RSA\s+PRIVATE\s+KEY)",  # PEM keys
                
                # Database connection strings
                r"(mysql|postgres|mongodb)://[^@]+:[^@]+@",
                r"jdbc:[^:]+://[^:]+:[^@]+@",
                
                # Cloud service patterns
                r"AKIA[0-9A-Z]{16}",  # AWS access keys
                r"sk_live_[0-9a-zA-Z]{24}",  # Stripe keys
                r"xox[baprs]-[0-9a-zA-Z-]{10,}",  # Slack tokens
            ]
            
            import re
            for pattern in credential_patterns:
                if re.search(pattern, data, re.IGNORECASE | re.MULTILINE):
                    if self.logger:
                        self.logger.warning(f"Potential credential pattern detected: {pattern[:20]}...")
                    return True
            
            # Entropy analysis for random-looking strings
            if self._has_high_entropy(data):
                if self.logger:
                    self.logger.warning("High entropy content detected - possible credential")
                return True
            
            # Check for common weak passwords in plaintext
            weak_passwords = {
                'password', 'password123', '123456', 'admin', 'root', 'guest',
                'qwerty', 'abc123', 'welcome', 'letmein', 'monkey', 'dragon'
            }
            
            words = re.findall(r'\b\w+\b', data_lower)
            for word in words:
                if word in weak_passwords:
                    if self.logger:
                        self.logger.warning(f"Weak password detected: {word}")
                    return True
                    
            return False

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in credential detection: {e}")
            return True  # Assume credentials present if detection fails
    
    def _has_high_entropy(self, data: str, threshold: float = 4.5) -> bool:
        """Check if string has high entropy (possibly encrypted/encoded content)"""
        try:
            if len(data) < 10:  # Too short to be meaningful
                return False
                
            import math
            from collections import Counter
            
            # Calculate Shannon entropy
            counter = Counter(data)
            length = len(data)
            entropy = -sum((count / length) * math.log2(count / length) 
                          for count in counter.values())
            
            return entropy > threshold
        except Exception:
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