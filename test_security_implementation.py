#!/usr/bin/env python3
"""
Test script to verify the security encryption implementation
"""

import json
import sys

sys.path.append("/home/amd/workspace/rock3399/digital-signage/src")

from src.domain.configuration import SecurityConfig
from src.infrastructure.security import SecurityService


def test_encryption_implementation():
    """Test the current encryption implementation"""
    print("Testing Security Service Implementation...")

    # Create security config
    config = SecurityConfig(
        session_timeout=3600,
        max_failed_attempts=3,
        owner_setup_timeout=300,
        require_owner_setup=True,
        key_rotation_interval=3600,
        max_key_age=86400,
    )

    # Create security service
    security_service = SecurityService(config)

    # Test 1: Basic encryption/decryption
    print("\n1. Testing basic encryption/decryption...")
    test_data = "test sensitive data"

    encrypt_result = security_service.encrypt_data(test_data)
    if encrypt_result.is_success():
        print("✅ Encryption successful")
        encrypted_data = encrypt_result.value

        # Test decryption
        decrypt_result = security_service.decrypt_data(encrypted_data)
        if decrypt_result.is_success():
            decrypted_data = decrypt_result.value
            if decrypted_data == test_data:
                print("✅ Decryption successful - data matches")
            else:
                print("❌ Decryption failed - data mismatch")
        else:
            print(f"❌ Decryption failed: {decrypt_result.error}")
    else:
        print(f"❌ Encryption failed: {encrypt_result.error}")

    # Test 2: Plaintext credential detection
    print("\n2. Testing plaintext credential detection...")
    plaintext_creds = '{"ssid": "TestWiFi", "password": "testpass123"}'

    if security_service.detect_plaintext_credentials(plaintext_creds):
        print("✅ Plaintext credentials detected correctly")
    else:
        print("❌ Failed to detect plaintext credentials")

    # Test 3: Session creation and key management
    print("\n3. Testing session management...")
    session_result = security_service.create_session("test-client")
    if session_result.is_success():
        session_id = session_result.value
        print(f"✅ Session created: {session_id}")

        # Test encryption with session key
        encrypt_with_session = security_service.encrypt_data(test_data, session_id)
        if encrypt_with_session.is_success():
            print("✅ Encryption with session key successful")
        else:
            print(f"❌ Session encryption failed: {encrypt_with_session.error}")
    else:
        print(f"❌ Session creation failed: {session_result.error}")

    # Test 4: Encryption compliance enforcement
    print("\n4. Testing encryption compliance...")
    sensitive_data = "password: secret123"
    compliance_result = security_service._enforce_encryption_compliance(sensitive_data)
    if compliance_result.is_failure():
        print("✅ Encryption compliance properly enforced")
    else:
        print("❌ Encryption compliance not enforced")

    print("\n5. Testing credential validation...")
    valid_result = security_service.validate_credentials("TestSSID", "validpassword123")
    if valid_result.is_success() and valid_result.value:
        print("✅ Credential validation working")
    else:
        print("❌ Credential validation failed")

    # Test plaintext rejection
    print("\n6. Testing plaintext credential rejection...")
    plaintext_data = '{"ssid": "TestNetwork", "password": "plaintext"}'
    encrypt_plaintext = security_service.encrypt_data(plaintext_data)
    if encrypt_plaintext.is_failure():
        print("✅ Plaintext credentials properly rejected")
    else:
        print("❌ Plaintext credentials not rejected")


if __name__ == "__main__":
    test_encryption_implementation()
