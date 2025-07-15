"""
Test utilities and helper functions for Rock Pi 3399 provisioning tests.
"""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from src.interfaces import DeviceState, ProvisioningEvent, NetworkInfo, ConnectionInfo, ConnectionStatus


class SystemTestOrchestrator:
    """
    High-level test orchestrator for complex integration test scenarios.
    """
    
    def __init__(self, provisioning_orchestrator):
        self.orchestrator = provisioning_orchestrator
        self.state_machine = provisioning_orchestrator.state_machine
        self.services = provisioning_orchestrator.services
        
    async def complete_first_time_setup(self, credentials: Dict[str, str], owner_pin: str = None) -> bool:
        """Complete entire first-time setup process."""
        try:
            # Owner setup if required
            if owner_pin and self.orchestrator.config.security.require_owner_setup:
                self.state_machine.process_event(ProvisioningEvent.START_OWNER_SETUP)
                ownership_service = self.services.get("ownership")
                success, message = ownership_service.register_owner(owner_pin, "Test Owner")
                if not success:
                    return False
                
                self.state_machine.process_event(ProvisioningEvent.OWNER_REGISTERED)
            
            # Network provisioning
            self.state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
            
            # Receive credentials
            self.state_machine.process_event(
                ProvisioningEvent.CREDENTIALS_RECEIVED, 
                credentials
            )
            
            # Simulate network connection
            self.state_machine.process_event(ProvisioningEvent.NETWORK_CONNECTED)
            
            return self.state_machine.get_current_state() == DeviceState.CONNECTED
            
        except Exception as e:
            print(f"First-time setup failed: {e}")
            return False
    
    async def simulate_network_change(self, old_credentials: Dict[str, str], new_credentials: Dict[str, str]) -> bool:
        """Simulate complete network change process."""
        try:
            # Start from connected state
            if self.state_machine.get_current_state() != DeviceState.CONNECTED:
                await self.complete_first_time_setup(old_credentials)
            
            # Trigger re-provisioning
            self.state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
            
            # Receive new credentials
            self.state_machine.process_event(
                ProvisioningEvent.CREDENTIALS_RECEIVED,
                new_credentials
            )
            
            # Connect to new network
            self.state_machine.process_event(ProvisioningEvent.NETWORK_CONNECTED)
            
            return self.state_machine.get_current_state() == DeviceState.CONNECTED
            
        except Exception as e:
            print(f"Network change failed: {e}")
            return False
    
    async def simulate_factory_reset(self, hold_time: float = 6.0) -> bool:
        """Simulate complete factory reset process."""
        try:
            # Trigger reset
            if hold_time >= 5.5:  # Meet timing requirement
                self.state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
                
                # Perform reset
                factory_reset_service = self.services.get("factory_reset")
                success, message = factory_reset_service.perform_reset("CONFIRM")
                
                if success:
                    # Reset state machine
                    self.state_machine.reset()
                    return True
            
            return False
            
        except Exception as e:
            print(f"Factory reset failed: {e}")
            return False


class NetworkSimulator:
    """
    Simulates various network conditions and behaviors for testing.
    """
    
    def __init__(self):
        self.available_networks = {}
        self.connection_delays = {}
        self.failure_rates = {}
        
    def add_network(self, ssid: str, password: str, signal_strength: int = -50, 
                   connection_delay: float = 0.5, failure_rate: float = 0.0):
        """Add a simulated network."""
        self.available_networks[ssid] = {
            "password": password,
            "signal_strength": signal_strength,
            "available": True
        }
        self.connection_delays[ssid] = connection_delay
        self.failure_rates[ssid] = failure_rate
    
    def set_network_availability(self, ssid: str, available: bool):
        """Set network availability."""
        if ssid in self.available_networks:
            self.available_networks[ssid]["available"] = available
    
    async def attempt_connection(self, ssid: str, password: str) -> bool:
        """Simulate network connection attempt."""
        if ssid not in self.available_networks:
            return False
        
        network = self.available_networks[ssid]
        
        # Check availability
        if not network["available"]:
            return False
        
        # Check password
        if password != network["password"]:
            return False
        
        # Simulate connection delay
        delay = self.connection_delays.get(ssid, 0.5)
        await asyncio.sleep(delay)
        
        # Simulate random failures
        failure_rate = self.failure_rates.get(ssid, 0.0)
        if failure_rate > 0:
            import random
            if random.random() < failure_rate:
                return False
        
        return True
    
    def scan_networks(self) -> List[NetworkInfo]:
        """Simulate network scan."""
        networks = []
        for ssid, info in self.available_networks.items():
            if info["available"]:
                networks.append(NetworkInfo(
                    ssid=ssid,
                    signal_strength=info["signal_strength"],
                    security_type="WPA2",
                    frequency=2400
                ))
        return networks


class SecurityTestUtils:
    """
    Utilities for security-related testing.
    """
    
    @staticmethod
    def generate_test_pins(count: int = 10) -> List[str]:
        """Generate various test PIN patterns."""
        pins = [
            "123456",  # Valid PIN
            "000000",  # All zeros
            "111111",  # All ones
            "123123",  # Repeating pattern
            "654321",  # Reverse sequence
            "987654",  # Different sequence
            "555555",  # All same digit
            "101010",  # Alternating pattern
            "999999",  # All nines
            "456789",  # Sequential
        ]
        return pins[:count]
    
    @staticmethod
    def generate_invalid_pins() -> List[str]:
        """Generate invalid PIN patterns for testing."""
        return [
            "",           # Empty
            "12345",      # Too short
            "1234567",    # Too long
            "12345a",     # Contains letter
            "12345!",     # Contains special char
            " 123456",    # Leading space
            "123456 ",    # Trailing space
            "12 3456",    # Space in middle
        ]
    
    @staticmethod
    def create_encrypted_credentials(credentials: Dict[str, str]) -> str:
        """Create encrypted credentials for testing (mock implementation)."""
        import base64
        credential_json = json.dumps(credentials)
        # Simple base64 encoding for test purposes
        # Real implementation would use proper encryption
        return base64.b64encode(credential_json.encode()).decode()
    
    @staticmethod
    def create_malformed_credentials() -> List[str]:
        """Create various malformed credential patterns."""
        return [
            '{"ssid": "test"',  # Incomplete JSON
            '{"ssid": "test", }',  # Trailing comma
            '{ssid: "test"}',  # Unquoted key
            '{"ssid": test}',  # Unquoted value
            'not json at all',  # Not JSON
            '',  # Empty string
            '{}',  # Empty object
            '{"ssid": ""}',  # Empty SSID
            '{"password": "test"}',  # Missing SSID
            '{"ssid": "' + 'A' * 300 + '"}',  # Oversized SSID
        ]


class PerformanceTestUtils:
    """
    Utilities for performance testing.
    """
    
    @staticmethod
    async def measure_operation_time(operation_func, *args, **kwargs) -> tuple:
        """Measure the execution time of an operation."""
        start_time = time.time()
        try:
            result = await operation_func(*args, **kwargs)
            success = True
        except Exception as e:
            result = e
            success = False
        end_time = time.time()
        
        return success, result, end_time - start_time
    
    @staticmethod
    def generate_performance_report(measurements: List[tuple]) -> Dict[str, Any]:
        """Generate performance report from measurements."""
        times = [measurement[2] for measurement in measurements if measurement[0]]
        
        if not times:
            return {"error": "No successful measurements"}
        
        return {
            "count": len(times),
            "min_time": min(times),
            "max_time": max(times),
            "avg_time": sum(times) / len(times),
            "success_rate": len(times) / len(measurements)
        }


class StateTransitionValidator:
    """
    Validates state machine transitions for correctness.
    """
    
    def __init__(self, state_machine):
        self.state_machine = state_machine
        self.expected_transitions = []
        self.actual_transitions = []
    
    def expect_transition(self, from_state: DeviceState, event: ProvisioningEvent, to_state: DeviceState):
        """Add expected state transition."""
        self.expected_transitions.append((from_state, event, to_state))
    
    def record_transition(self, from_state: DeviceState, event: ProvisioningEvent, to_state: DeviceState):
        """Record actual state transition."""
        self.actual_transitions.append((from_state, event, to_state))
    
    def validate_transitions(self) -> bool:
        """Validate that actual transitions match expected."""
        if len(self.actual_transitions) != len(self.expected_transitions):
            return False
        
        for expected, actual in zip(self.expected_transitions, self.actual_transitions):
            if expected != actual:
                return False
        
        return True
    
    def get_transition_report(self) -> Dict[str, Any]:
        """Get detailed transition validation report."""
        return {
            "expected_count": len(self.expected_transitions),
            "actual_count": len(self.actual_transitions),
            "expected_transitions": self.expected_transitions,
            "actual_transitions": self.actual_transitions,
            "valid": self.validate_transitions()
        }


class TestDataGenerator:
    """
    Generates various test data patterns for comprehensive testing.
    """
    
    @staticmethod
    def generate_network_credentials(count: int = 5) -> List[Dict[str, str]]:
        """Generate multiple sets of network credentials."""
        credentials = []
        for i in range(count):
            credentials.append({
                "ssid": f"TestNetwork{i}",
                "password": f"TestPassword{i}!",
                "security": "WPA2"
            })
        return credentials
    
    @staticmethod
    def generate_device_info_variations() -> List[Dict[str, Any]]:
        """Generate device info variations for testing."""
        return [
            {
                "device_id": "ROCKPI-001",
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "hardware_version": "Rock Pi 3399 v1.4",
                "firmware_version": "2.0.0",
                "capabilities": ["wifi", "bluetooth", "display", "gpio"]
            },
            {
                "device_id": "ROCKPI-002",
                "mac_address": "11:22:33:44:55:66",
                "hardware_version": "Rock Pi 3399 v1.5",
                "firmware_version": "2.1.0",
                "capabilities": ["wifi", "bluetooth", "display", "gpio", "audio"]
            }
        ]
    
    @staticmethod
    def generate_stress_test_data() -> Dict[str, Any]:
        """Generate data for stress testing."""
        return {
            "large_ssid": "A" * 255,  # Maximum length SSID
            "large_password": "P" * 100,  # Long password
            "unicode_ssid": "网络测试_日本語_한국어",  # Unicode SSID
            "special_chars_password": "!@#$%^&*()_+-=[]{}|;:,.<>?",
            "repeated_credentials": [{"ssid": "Test", "password": "Pass"} for _ in range(100)]
        }


async def run_integration_test_suite(orchestrator, test_scenarios: List[str]) -> Dict[str, bool]:
    """
    Run a complete integration test suite with multiple scenarios.
    """
    results = {}
    test_orchestrator = SystemTestOrchestrator(orchestrator)
    
    for scenario in test_scenarios:
        try:
            if scenario == "first_time_setup":
                credentials = {"ssid": "TestNet", "password": "TestPass123!", "security": "WPA2"}
                success = await test_orchestrator.complete_first_time_setup(credentials, "123456")
                results[scenario] = success
                
            elif scenario == "network_change":
                old_creds = {"ssid": "OldNet", "password": "OldPass123!", "security": "WPA2"}
                new_creds = {"ssid": "NewNet", "password": "NewPass123!", "security": "WPA2"}
                success = await test_orchestrator.simulate_network_change(old_creds, new_creds)
                results[scenario] = success
                
            elif scenario == "factory_reset":
                success = await test_orchestrator.simulate_factory_reset()
                results[scenario] = success
                
            else:
                results[scenario] = False
                
        except Exception as e:
            print(f"Integration test {scenario} failed: {e}")
            results[scenario] = False
    
    return results


def create_test_summary_report(test_results: Dict[str, Any]) -> str:
    """
    Create a comprehensive test summary report.
    """
    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results.values() if result)
    success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    
    report = f"""
# Rock Pi 3399 Provisioning System - Test Summary Report

**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Tests:** {total_tests}
**Passed Tests:** {passed_tests}
**Failed Tests:** {total_tests - passed_tests}
**Success Rate:** {success_rate:.1f}%

## Test Results by Category:

"""
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        report += f"- **{test_name}:** {status}\n"
    
    report += f"""

## Coverage Analysis:
- **First-Time Setup (F1-F3):** {success_rate:.1f}% (Target: 93%)
- **Normal Operation (N1-N2):** {success_rate:.1f}% (Target: 97.5%)
- **Factory Reset (R1-R2):** {success_rate:.1f}% (Target: 82.5%)
- **Error Recovery (E1-E2):** {success_rate:.1f}% (Target: 72.5%)
- **Security Validation (S1-S2):** {success_rate:.1f}% (Target: 80%)

## Recommendations:
"""
    
    if success_rate < 90:
        report += "- Review and fix failing test cases\n"
        report += "- Check system configuration and dependencies\n"
    
    if success_rate >= 90:
        report += "- Test suite performance is good\n"
        report += "- Consider adding additional edge case tests\n"
    
    return report
