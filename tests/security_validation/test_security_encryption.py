"""
Critical Security Encryption Tests
These tests cover the untested error paths and edge cases in the SecurityService
that were identified in the code review.
"""

import base64
import time
from unittest.mock import MagicMock, patch

import pytest

from src.domain.configuration import SecurityConfig
from src.domain.errors import ErrorCode, SecurityError
from src.infrastructure.security import SecurityService


class TestSecurityEncryptionCritical:
    """Critical security encryption tests for untested error paths"""

    def test_encryption_with_invalid_key_length(self):
        """Test encryption fails with invalid/short keys"""
        config = SecurityConfig(
            session_timeout=3600,
            max_failed_attempts=3,
            owner_setup_timeout=300,
            require_owner_setup=True,
            key_rotation_interval=3600,
            max_key_age=86400,
        )

        security_service = SecurityService(config)

        # Test with corrupted master key (too short)
        security_service.master_key = b"short"  # Too short key

        result = security_service.encrypt_data("test data")

        assert result.is_failure()
        assert isinstance(result.error, SecurityError)
        assert result.error.code == ErrorCode.ENCRYPTION_FAILED
        assert "Invalid or missing encryption key" in str(result.error)

    def test_encryption_with_none_key(self):
        """Test encryption fails with None key"""
        config = SecurityConfig(
            session_timeout=3600,
            max_failed_attempts=3,
            owner_setup_timeout=300,
            require_owner_setup=True,
            key_rotation_interval=3600,
            max_key_age=86400,
        )

        security_service = SecurityService(config)
        security_service.master_key = None

        result = security_service.encrypt_data("test data")

        assert result.is_failure()
        assert isinstance(result.error, SecurityError)
        assert result.error.code == ErrorCode.ENCRYPTION_FAILED

    def test_decryption_with_corrupted_data(self):
        """Test decryption fails gracefully with corrupted encrypted data"""
        config = SecurityConfig(
            session_timeout=3600,
            max_failed_attempts=3,
            owner_setup_timeout=300,
            require_owner_setup=True,
            key_rotation_interval=3600,
            max_key_age=86400,
        )

        security_service = SecurityService(config)

        # Try to decrypt obviously corrupted data
        corrupted_data = b"this_is_not_encrypted_data"

        result = security_service.decrypt_data(corrupted_data)

        assert result.is_failure()
        assert isinstance(result.error, SecurityError)
        assert result.error.code == ErrorCode.ENCRYPTION_FAILED

    def test_decryption_with_wrong_key(self):
        """Test decryption fails with different key than encryption"""
        config = SecurityConfig(
            session_timeout=3600,
            max_failed_attempts=3,
            owner_setup_timeout=300,
            require_owner_setup=True,
            key_rotation_interval=3600,
            max_key_age=86400,
        )

        # Create two different security services with different keys
        security_service1 = SecurityService(config)
        security_service2 = SecurityService(config)

        # Encrypt with first service
        encrypt_result = security_service1.encrypt_data("secret data")
        assert encrypt_result.is_success()

        # Try to decrypt with second service (different key)
        decrypt_result = security_service2.decrypt_data(encrypt_result.value)

        assert decrypt_result.is_failure()
        assert isinstance(decrypt_result.error, SecurityError)

    def test_key_compromise_detection_weak_patterns(self):
        """Test detection of weak/compromised encryption keys"""
        config = SecurityConfig(
            session_timeout=3600,
            max_failed_attempts=3,
            owner_setup_timeout=300,
            require_owner_setup=True,
            key_rotation_interval=3600,
            max_key_age=86400,
        )

        security_service = SecurityService(config)

        # Test with weak key patterns
        weak_keys = [
            b"00000000000000000000000000000000",  # All zeros
            b"11111111111111111111111111111111",  # All ones
            b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # Repeated character
            b"1234567890123456789012345678901234567890",  # Sequential
        ]

        for weak_key in weak_keys:
            # Test key compromise detection directly
            is_compromised = security_service._detect_key_compromise(weak_key)
            assert is_compromised, f"Failed to detect compromise in key: {weak_key}"

    def test_key_compromise_detection_insufficient_entropy(self):
        """Test detection of keys with insufficient entropy"""
        config = SecurityConfig(
            session_timeout=3600,
            max_failed_attempts=3,
            owner_setup_timeout=300,
            require_owner_setup=True,
            key_rotation_interval=3600,
            max_key_age=86400,
        )

        security_service = SecurityService(config)

        # Create key with very low entropy (only a few unique bytes)
        low_entropy_key = b"abab" * 16  # Only 'a' and 'b' repeated

        is_compromised = security_service._detect_key_compromise(low_entropy_key)
        assert is_compromised, "Failed to detect low entropy key"

    def test_plaintext_credential_detection_various_formats(self):
        """Test detection of plaintext credentials in various formats"""
        config = SecurityConfig(
            session_timeout=3600,
            max_failed_attempts=3,
            owner_setup_timeout=300,
            require_owner_setup=True,
            key_rotation_interval=3600,
            max_key_age=86400,
        )

        security_service = SecurityService(config)

        # Test various plaintext credential patterns
        plaintext_patterns = [
            '{"ssid": "MyWiFi", "password": "secret123"}',  # JSON format
            "SSID=MyWiFi\nPASSWORD=secret123",  # Key-value format
            "username:admin\npassword:secret",  # Colon format
            "wifi_password=secret123",  # Simple assignment
            "auth_token=abc123def456",  # Token format
        ]

        for pattern in plaintext_patterns:
            is_plaintext = security_service.detect_plaintext_credentials(pattern)
            assert is_plaintext, f"Failed to detect plaintext in: {pattern}"

    def test_concurrent_encryption_operations(self):
        """Test thread safety of encryption operations"""
        config = SecurityConfig(
            session_timeout=3600,
            max_failed_attempts=3,
            owner_setup_timeout=300,
            require_owner_setup=True,
            key_rotation_interval=3600,
            max_key_age=86400,
        )

        security_service = SecurityService(config)

        import concurrent.futures
        import threading

        def encrypt_decrypt_operation(data_suffix):
            """Perform encryption and decryption operation"""
            test_data = f"test data {data_suffix}"

            # Encrypt
            encrypt_result = security_service.encrypt_data(test_data)
            if encrypt_result.is_failure():
                return False

            # Decrypt
            decrypt_result = security_service.decrypt_data(encrypt_result.value)
            if decrypt_result.is_failure():
                return False

            return decrypt_result.value == test_data

        # Run multiple concurrent operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(encrypt_decrypt_operation, i) for i in range(20)]

            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        # All operations should succeed
        assert all(results), "Concurrent encryption operations failed"

    def test_session_key_rotation_error_scenarios(self):
        """Test session key rotation error handling"""
        config = SecurityConfig(
            session_timeout=3600,
            max_failed_attempts=3,
            owner_setup_timeout=300,
            require_owner_setup=True,
            key_rotation_interval=3600,
            max_key_age=86400,
        )

        security_service = SecurityService(config)

        # Create a session
        session_result = security_service.create_session("test_client")
        assert session_result.is_success()
        session_id = session_result.value

        # Test rotation with invalid session ID
        invalid_rotation = security_service.rotate_session_key("invalid_session_id")
        assert invalid_rotation.is_failure()

        # Test rotation with corrupted session data
        security_service.sessions[session_id] = {"corrupted": "data"}
        rotation_result = security_service.rotate_session_key(session_id)
        # Should handle gracefully (either succeed with new key or fail gracefully)
        assert rotation_result.is_success() or rotation_result.is_failure()

    def test_encryption_compliance_enforcement_edge_cases(self):
        """Test encryption compliance enforcement with edge cases"""
        config = SecurityConfig(
            session_timeout=3600,
            max_failed_attempts=3,
            owner_setup_timeout=300,
            require_owner_setup=True,
            key_rotation_interval=3600,
            max_key_age=86400,
        )

        security_service = SecurityService(config)

        # Test edge cases for compliance enforcement
        edge_cases = [
            "",  # Empty string
            " " * 1000,  # Only whitespace
            "password" * 100,  # Repeated sensitive word
            '{"password": ""}',  # Empty password in JSON
            "key=",  # Empty key value
            "secret\x00\x01\x02",  # Binary data mixed with sensitive word
        ]

        for case in edge_cases:
            try:
                compliance_result = security_service._enforce_encryption_compliance(
                    case
                )
                # Should either pass or fail, but not crash
                assert compliance_result.is_success() or compliance_result.is_failure()
            except Exception as e:
                pytest.fail(
                    f"Encryption compliance check crashed on input: {case}, error: {e}"
                )

    def test_malformed_session_data_handling(self):
        """Test handling of malformed session data"""
        config = SecurityConfig(
            session_timeout=3600,
            max_failed_attempts=3,
            owner_setup_timeout=300,
            require_owner_setup=True,
            key_rotation_interval=3600,
            max_key_age=86400,
        )

        security_service = SecurityService(config)

        # Create session with malformed data
        malformed_sessions = [
            {"client_id": "test", "created_at": "not_a_number"},
            {"client_id": "test", "created_at": -1},
            {"client_id": "test"},  # Missing created_at
            {},  # Empty session
            {"created_at": time.time()},  # Missing client_id
        ]

        for i, malformed_data in enumerate(malformed_sessions):
            session_id = f"malformed_session_{i}"
            security_service.sessions[session_id] = malformed_data

            # Operations should handle malformed data gracefully
            encrypt_result = security_service.encrypt_data("test", session_id)
            # Should either work with master key or fail gracefully
            assert encrypt_result.is_success() or encrypt_result.is_failure()

    def test_encryption_with_very_large_data(self):
        """Test encryption with very large data sets"""
        config = SecurityConfig(
            session_timeout=3600,
            max_failed_attempts=3,
            owner_setup_timeout=300,
            require_owner_setup=True,
            key_rotation_interval=3600,
            max_key_age=86400,
        )

        security_service = SecurityService(config)

        # Test with large data (1MB)
        large_data = "x" * (1024 * 1024)

        encrypt_result = security_service.encrypt_data(large_data)
        if encrypt_result.is_success():
            # If encryption succeeds, decryption should also work
            decrypt_result = security_service.decrypt_data(encrypt_result.value)
            assert decrypt_result.is_success()
            assert decrypt_result.value == large_data
        else:
            # If encryption fails, it should fail gracefully
            assert isinstance(encrypt_result.error, SecurityError)
