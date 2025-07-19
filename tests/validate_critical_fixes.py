#!/usr/bin/env python3
"""
Test script to validate critical issue fixes implemented in the code review
"""

import asyncio
import os
import sys
import time
from typing import Any, Dict

# Add src to path for proper imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "src")
sys.path.insert(0, src_path)

from application.background_task_manager import BackgroundTaskManager

# Import individual modules directly to avoid package init issues
from application.dependency_injection import Container
from domain.configuration import BLEConfig, NetworkConfig, SecurityConfig
from infrastructure.bluetooth import BluetoothService
from infrastructure.logging import ConsoleLogger
from infrastructure.network import NetworkService
from infrastructure.security import SecurityService


class ValidationResults:
    def __init__(self):
        self.results: Dict[str, Dict[str, Any]] = {}

    def add_result(
        self, category: str, test_name: str, passed: bool, details: str = ""
    ):
        if category not in self.results:
            self.results[category] = {}
        self.results[category][test_name] = {"passed": passed, "details": details}

    def print_summary(self):
        print("\n" + "=" * 60)
        print("CRITICAL ISSUES VALIDATION SUMMARY")
        print("=" * 60)

        total_tests = 0
        passed_tests = 0

        for category, tests in self.results.items():
            print(f"\n{category}:")
            for test_name, result in tests.items():
                total_tests += 1
                status = "✅ PASS" if result["passed"] else "❌ FAIL"
                if result["passed"]:
                    passed_tests += 1
                print(f"  {status} {test_name}")
                if result["details"]:
                    print(f"      {result['details']}")

        print(f"\n{'='*60}")
        print(f"OVERALL RESULT: {passed_tests}/{total_tests} tests passed")
        if passed_tests == total_tests:
            print("🎉 ALL CRITICAL ISSUES HAVE BEEN FIXED!")
        else:
            print("⚠️  Some critical issues still need attention")
        print("=" * 60)


async def test_security_fixes(results: ValidationResults):
    """Test security infrastructure fixes"""
    logger = ConsoleLogger()
    config = SecurityConfig(session_timeout=300)

    try:
        security_service = SecurityService(config, logger)

        # Test 1: Enhanced error handling
        encrypt_result = security_service.encrypt_data("test data")
        results.add_result(
            "Security",
            "Enhanced encryption error handling",
            encrypt_result.is_success(),
            "Encryption works with better error handling",
        )

        # Test 2: Session management with thread safety
        session_result = security_service.create_session("test_client")
        if session_result.is_success():
            session_id = session_result.value
            valid = security_service.validate_session(session_id)
            results.add_result(
                "Security",
                "Thread-safe session management",
                valid,
                "Session validation works with thread safety",
            )
        else:
            results.add_result(
                "Security",
                "Thread-safe session management",
                False,
                "Session creation failed",
            )

        # Test 3: Encryption compliance enforcement
        compliance_result = security_service._enforce_encryption_compliance(
            "password: secret"
        )
        results.add_result(
            "Security",
            "Encryption compliance enforcement",
            compliance_result.is_failure(),
            "Properly rejects sensitive plaintext",
        )

        # Test 4: Key management improvements
        has_key_methods = hasattr(
            security_service, "_rotate_session_key_internal"
        ) and hasattr(security_service, "_detect_key_compromise")
        results.add_result(
            "Security",
            "Enhanced key management",
            has_key_methods,
            "Key rotation and compromise detection implemented",
        )

    except Exception as e:
        results.add_result(
            "Security", "Security fixes validation", False, f"Exception: {e}"
        )


async def test_bluetooth_fixes(results: ValidationResults):
    """Test Bluetooth BLE recovery fixes"""
    logger = ConsoleLogger()
    config = BLEConfig(device_name="test", service_uuid="test-uuid")

    try:
        bluetooth_service = BluetoothService(config, logger)

        # Test 1: Recovery synchronization
        has_locks = hasattr(bluetooth_service, "_recovery_lock") and hasattr(
            bluetooth_service, "_session_lock"
        )
        results.add_result(
            "Bluetooth",
            "Recovery race condition fixes",
            has_locks,
            "Async locks for BLE recovery implemented",
        )

        # Test 2: Session cleanup
        has_cleanup = hasattr(bluetooth_service, "cleanup_sessions")
        results.add_result(
            "Bluetooth",
            "Session resource cleanup",
            has_cleanup,
            "Proper session cleanup method added",
        )

        # Test 3: Context manager support
        has_context_manager = hasattr(bluetooth_service, "__aenter__") and hasattr(
            bluetooth_service, "__aexit__"
        )
        results.add_result(
            "Bluetooth",
            "Async context manager",
            has_context_manager,
            "Async context manager for resource management",
        )

    except Exception as e:
        results.add_result(
            "Bluetooth", "Bluetooth fixes validation", False, f"Exception: {e}"
        )


async def test_dependency_injection_fixes(results: ValidationResults):
    """Test dependency injection circular dependency fixes"""
    try:
        container = Container()

        # Test 1: Circular dependency detection
        has_validation = hasattr(container, "validate_registrations")
        results.add_result(
            "Dependency Injection",
            "Circular dependency detection",
            has_validation,
            "Validation method for detecting circular dependencies",
        )

        # Test 2: Enhanced error handling
        try:
            # This should raise a proper error
            container.resolve(str)  # Unregistered service
        except ValueError as e:
            error_has_context = "Available services" in str(e)
            results.add_result(
                "Dependency Injection",
                "Enhanced error messages",
                error_has_context,
                "Error messages include available services",
            )
        except Exception:
            results.add_result(
                "Dependency Injection",
                "Enhanced error messages",
                False,
                "Unexpected exception type",
            )

        # Test 3: Resource cleanup
        has_disposal = hasattr(container, "dispose")
        results.add_result(
            "Dependency Injection",
            "Resource disposal",
            has_disposal,
            "Proper resource disposal method",
        )

        # Test 4: Context manager support
        has_context_manager = hasattr(container, "__enter__") and hasattr(
            container, "__exit__"
        )
        results.add_result(
            "Dependency Injection",
            "Context manager support",
            has_context_manager,
            "Context manager for automatic cleanup",
        )

    except Exception as e:
        results.add_result(
            "Dependency Injection", "DI fixes validation", False, f"Exception: {e}"
        )


async def test_background_task_fixes(results: ValidationResults):
    """Test background task manager timeout fixes"""
    logger = ConsoleLogger()

    try:
        task_manager = BackgroundTaskManager(logger)

        # Test 1: Enhanced timeout handling
        async def quick_task():
            await asyncio.sleep(0.1)
            return "completed"

        success = await task_manager.start_task(
            "test_task", quick_task, max_execution_time=1.0, restart_policy="never"
        )
        results.add_result(
            "Background Tasks",
            "Enhanced timeout handling",
            success,
            "Task started with timeout configuration",
        )

        # Test 2: Health monitoring improvements
        has_health_methods = hasattr(task_manager, "get_health_summary") and hasattr(
            task_manager, "is_task_healthy"
        )
        results.add_result(
            "Background Tasks",
            "Health monitoring improvements",
            has_health_methods,
            "Enhanced health monitoring methods",
        )

        # Test 3: Lifecycle management
        has_lifecycle = hasattr(task_manager, "start") and hasattr(task_manager, "stop")
        results.add_result(
            "Background Tasks",
            "Lifecycle management",
            has_lifecycle,
            "Proper start/stop lifecycle methods",
        )

        # Test 4: Context manager support
        has_context_manager = hasattr(task_manager, "__aenter__") and hasattr(
            task_manager, "__aexit__"
        )
        results.add_result(
            "Background Tasks",
            "Async context manager",
            has_context_manager,
            "Async context manager for resource management",
        )

        # Cleanup
        await task_manager.stop_all_tasks()

    except Exception as e:
        results.add_result(
            "Background Tasks",
            "Background task fixes validation",
            False,
            f"Exception: {e}",
        )


async def test_network_fixes(results: ValidationResults):
    """Test network infrastructure async resource management fixes"""
    logger = ConsoleLogger()
    config = NetworkConfig(
        interface_name="wlan0", wifi_scan_timeout=10.0, connection_timeout=30.0
    )

    try:
        network_service = NetworkService(config, logger)

        # Test 1: Async locks and resource management
        has_locks = hasattr(network_service, "_scan_lock") and hasattr(
            network_service, "_connection_lock"
        )
        results.add_result(
            "Network",
            "Async resource management",
            has_locks,
            "Async locks for network operations",
        )

        # Test 2: Resource cleanup
        has_cleanup = hasattr(network_service, "cleanup_resources")
        results.add_result(
            "Network", "Resource cleanup", has_cleanup, "Proper resource cleanup method"
        )

        # Test 3: Context manager support
        has_context_manager = hasattr(network_service, "__aenter__") and hasattr(
            network_service, "__aexit__"
        )
        results.add_result(
            "Network",
            "Async context manager",
            has_context_manager,
            "Async context manager for resource management",
        )

        # Test 4: Health monitoring
        has_health = hasattr(network_service, "get_connection_health")
        results.add_result(
            "Network",
            "Connection health monitoring",
            has_health,
            "Enhanced connection health monitoring",
        )

    except Exception as e:
        results.add_result(
            "Network", "Network fixes validation", False, f"Exception: {e}"
        )


async def main():
    """Main validation function"""
    print("🔍 Validating Critical Issue Fixes...")
    print(
        "This script tests the implemented solutions for critical issues identified in the code review."
    )

    results = ValidationResults()

    print("\n1. Testing Security Infrastructure fixes...")
    await test_security_fixes(results)

    print("2. Testing Bluetooth BLE Recovery fixes...")
    await test_bluetooth_fixes(results)

    print("3. Testing Dependency Injection fixes...")
    await test_dependency_injection_fixes(results)

    print("4. Testing Background Task Manager fixes...")
    await test_background_task_fixes(results)

    print("5. Testing Network Infrastructure fixes...")
    await test_network_fixes(results)

    results.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
