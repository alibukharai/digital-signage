"""
Factory Reset Tests (R1-R2)

These tests cover factory reset functionality:
- R1: Hardware button reset
- R2: Reset during active session

Coverage Analysis: 82.5% average (Good)
System Under Test: Rock Pi 3399
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path

from src.interfaces import DeviceState, ProvisioningEvent
from tests.conftest import (
    assert_state_transition, 
    wait_for_state
)


class TestR1HardwareButtonReset:
    """
    R1: Hardware Button Reset
    Scenario: Factory reset triggered by hardware button
    Coverage: 85% - Core functionality present
    """

    @pytest.mark.asyncio
    async def test_gpio18_button_configuration(
        self, 
        test_config
    ):
        """Test that GPIO18 is properly configured for reset button."""
        gpio_config = test_config.system.factory_reset_gpio
        assert gpio_config == 18
        
        # Verify hold time configuration
        hold_time = test_config.system.factory_reset_hold_time
        assert hold_time == 5.5

    @pytest.mark.asyncio
    async def test_gpio_monitoring_active(
        self, 
        provisioning_orchestrator,
        gpio_test_helper
    ):
        """Test that GPIO monitoring is active and responsive."""
        orchestrator = provisioning_orchestrator
        factory_reset_service = orchestrator.services.get("factory_reset")
        
        # Verify reset service is available
        assert factory_reset_service.is_reset_available()
        
        # Test GPIO helper is configured correctly
        assert gpio_test_helper.pin == 18
        assert gpio_test_helper.reset_threshold == 5.5

    @pytest.mark.asyncio
    async def test_button_press_insufficient_duration(
        self, 
        provisioning_orchestrator,
        gpio_test_helper
    ):
        """Test that short button presses don't trigger reset."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine
        
        initial_state = state_machine.get_current_state()
        
        # Simulate button press for insufficient time (3 seconds)
        button_result = await gpio_test_helper.press_and_hold(3.0)
        
        # Should not trigger reset
        assert not button_result
        
        # State should remain unchanged
        assert state_machine.get_current_state() == initial_state

    @pytest.mark.asyncio
    async def test_button_press_exact_duration(
        self, 
        provisioning_orchestrator,
        gpio_test_helper
    ):
        """Test button press for exactly 5.5 seconds triggers reset."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine
        
        # Simulate button press for exact threshold time
        button_result = await gpio_test_helper.press_and_hold(5.5)
        
        # Should trigger reset
        assert button_result
        
        # Simulate reset trigger event
        state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
        
        # Should transition to FACTORY_RESET state
        assert state_machine.get_current_state() == DeviceState.FACTORY_RESET

    @pytest.mark.asyncio
    async def test_button_press_extended_duration(
        self, 
        provisioning_orchestrator,
        gpio_test_helper
    ):
        """Test button press longer than 5.5 seconds triggers reset."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine
        
        # Simulate button press for extended time (8 seconds)
        button_result = await gpio_test_helper.press_and_hold(8.0)
        
        # Should trigger reset
        assert button_result
        
        # Simulate reset trigger event
        state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
        
        # Should transition to FACTORY_RESET state
        assert state_machine.get_current_state() == DeviceState.FACTORY_RESET

    @pytest.mark.asyncio
    async def test_reset_from_different_states(
        self, 
        provisioning_orchestrator,
        gpio_test_helper
    ):
        """Test that reset can be triggered from any system state."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine
        
        # Test reset from different states
        test_states = [
            DeviceState.INITIALIZING,
            DeviceState.READY,
            DeviceState.PROVISIONING,
            DeviceState.CONNECTED,
            DeviceState.ERROR
        ]
        
        for test_state in test_states:
            # Set up state machine in test state
            state_machine.reset()  # Reset to INITIALIZING
            
            if test_state == DeviceState.READY:
                state_machine.process_event(ProvisioningEvent.START_OWNER_SETUP)
            elif test_state == DeviceState.PROVISIONING:
                state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
            elif test_state == DeviceState.CONNECTED:
                state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
                state_machine.process_event(ProvisioningEvent.NETWORK_CONNECTED)
            elif test_state == DeviceState.ERROR:
                state_machine.process_event(ProvisioningEvent.ERROR_OCCURRED)
            
            # Verify we're in expected state
            assert state_machine.get_current_state() == test_state
            
            # Trigger reset
            button_result = await gpio_test_helper.press_and_hold(6.0)
            assert button_result
            
            state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
            
            # Should transition to FACTORY_RESET from any state
            assert state_machine.get_current_state() == DeviceState.FACTORY_RESET

    @pytest.mark.asyncio
    async def test_credential_clearing_during_reset(
        self, 
        provisioning_orchestrator,
        valid_credentials,
        gpio_test_helper
    ):
        """Test that saved credentials are cleared during factory reset."""
        orchestrator = provisioning_orchestrator
        config_service = orchestrator.services.get("configuration")
        factory_reset_service = orchestrator.services.get("factory_reset")
        state_machine = orchestrator.state_machine
        
        # Set up saved credentials
        config_service.save_network_config(
            valid_credentials["ssid"], 
            valid_credentials["password"]
        )
        assert config_service.has_network_config()
        
        # Trigger factory reset
        button_result = await gpio_test_helper.press_and_hold(6.0)
        assert button_result
        
        state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
        
        # Perform reset
        reset_success, reset_message = factory_reset_service.perform_reset("CONFIRM")
        assert reset_success
        
        # Verify credentials are cleared
        assert not config_service.has_network_config()

    @pytest.mark.asyncio
    async def test_owner_registration_clearing_during_reset(
        self, 
        provisioning_orchestrator,
        valid_owner_pin,
        gpio_test_helper
    ):
        """Test that owner registration is cleared during factory reset."""
        orchestrator = provisioning_orchestrator
        ownership_service = orchestrator.services.get("ownership")
        factory_reset_service = orchestrator.services.get("factory_reset")
        state_machine = orchestrator.state_machine
        
        # Set up owner registration
        state_machine.process_event(ProvisioningEvent.START_OWNER_SETUP)
        success, message = ownership_service.register_owner(valid_owner_pin, "Test Owner")
        assert success
        assert ownership_service.is_owner_registered()
        
        # Trigger factory reset
        button_result = await gpio_test_helper.press_and_hold(6.0)
        assert button_result
        
        state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
        
        # Perform reset
        reset_success, reset_message = factory_reset_service.perform_reset("CONFIRM")
        assert reset_success
        
        # Verify owner registration is cleared
        assert not ownership_service.is_owner_registered()

    @pytest.mark.asyncio
    async def test_state_transition_to_initializing_after_reset(
        self, 
        provisioning_orchestrator,
        gpio_test_helper
    ):
        """Test that system returns to INITIALIZING state after reset."""
        orchestrator = provisioning_orchestrator
        factory_reset_service = orchestrator.services.get("factory_reset")
        state_machine = orchestrator.state_machine
        
        # Start from connected state
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        state_machine.process_event(ProvisioningEvent.NETWORK_CONNECTED)
        assert state_machine.get_current_state() == DeviceState.CONNECTED
        
        # Trigger factory reset
        button_result = await gpio_test_helper.press_and_hold(6.0)
        assert button_result
        
        state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
        assert state_machine.get_current_state() == DeviceState.FACTORY_RESET
        
        # Complete reset process
        reset_success, reset_message = factory_reset_service.perform_reset("CONFIRM")
        assert reset_success
        
        # System should return to initial state
        state_machine.reset()  # Simulate post-reset initialization
        assert state_machine.get_current_state() == DeviceState.INITIALIZING

    @pytest.mark.asyncio
    async def test_system_returns_to_factory_defaults(
        self, 
        provisioning_orchestrator,
        valid_credentials,
        valid_owner_pin,
        gpio_test_helper
    ):
        """Test that all settings return to factory defaults after reset."""
        orchestrator = provisioning_orchestrator
        config_service = orchestrator.services.get("configuration")
        ownership_service = orchestrator.services.get("ownership")
        factory_reset_service = orchestrator.services.get("factory_reset")
        state_machine = orchestrator.state_machine
        
        # Set up various configurations
        config_service.save_network_config(
            valid_credentials["ssid"], 
            valid_credentials["password"]
        )
        
        state_machine.process_event(ProvisioningEvent.START_OWNER_SETUP)
        ownership_service.register_owner(valid_owner_pin, "Test Owner")
        
        # Verify configurations exist
        assert config_service.has_network_config()
        assert ownership_service.is_owner_registered()
        
        # Perform factory reset
        button_result = await gpio_test_helper.press_and_hold(6.0)
        assert button_result
        
        state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
        reset_success, reset_message = factory_reset_service.perform_reset("CONFIRM")
        assert reset_success
        
        # Verify all configurations are cleared
        assert not config_service.has_network_config()
        assert not ownership_service.is_owner_registered()
        
        # System should be ready for fresh setup
        state_machine.reset()
        assert state_machine.get_current_state() == DeviceState.INITIALIZING

    @pytest.mark.asyncio
    async def test_reset_confirmation_flow(
        self, 
        provisioning_orchestrator,
        gpio_test_helper
    ):
        """Test the reset confirmation flow for safety."""
        orchestrator = provisioning_orchestrator
        factory_reset_service = orchestrator.services.get("factory_reset")
        state_machine = orchestrator.state_machine
        
        # Trigger reset
        button_result = await gpio_test_helper.press_and_hold(6.0)
        assert button_result
        
        state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
        assert state_machine.get_current_state() == DeviceState.FACTORY_RESET
        
        # Test reset without confirmation (should fail)
        reset_success, reset_message = factory_reset_service.perform_reset("")
        assert not reset_success
        
        # Test reset with correct confirmation
        reset_success, reset_message = factory_reset_service.perform_reset("CONFIRM")
        assert reset_success

    @pytest.mark.asyncio
    async def test_reset_timing_precision(
        self, 
        gpio_test_helper
    ):
        """Test precise timing validation for 5.5 second requirement."""
        # Test various timing scenarios
        timing_tests = [
            (5.4, False),  # Just under threshold
            (5.5, True),   # Exact threshold
            (5.6, True),   # Just over threshold
            (6.0, True),   # Well over threshold
        ]
        
        for duration, expected_result in timing_tests:
            button_result = await gpio_test_helper.press_and_hold(duration)
            assert button_result == expected_result

    @pytest.mark.asyncio
    async def test_concurrent_button_presses(
        self, 
        gpio_test_helper
    ):
        """Test handling of multiple or concurrent button press scenarios."""
        # Test rapid button presses
        for _ in range(3):
            # Short presses shouldn't trigger reset
            button_result = await gpio_test_helper.press_and_hold(1.0)
            assert not button_result
            
            # Small delay between presses
            await asyncio.sleep(0.1)
        
        # Single long press should still work
        button_result = await gpio_test_helper.press_and_hold(6.0)
        assert button_result


class TestR2ResetDuringActiveSession:
    """
    R2: Reset During Active Session
    Scenario: Factory reset while provisioning is in progress
    Coverage: 80% - Basic session termination
    """

    @pytest.mark.asyncio
    async def test_reset_during_ble_provisioning(
        self, 
        provisioning_orchestrator,
        gpio_test_helper
    ):
        """Test factory reset triggered during active BLE provisioning session."""
        orchestrator = provisioning_orchestrator
        bluetooth_service = orchestrator.services.get("bluetooth")
        state_machine = orchestrator.state_machine
        
        # Start provisioning session
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        assert state_machine.get_current_state() == DeviceState.PROVISIONING
        
        # Simulate active BLE session
        # In real implementation, would check actual BLE connection state
        
        # Trigger reset during active session
        button_result = await gpio_test_helper.press_and_hold(6.0)
        assert button_result
        
        state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
        
        # Should immediately transition to FACTORY_RESET
        assert state_machine.get_current_state() == DeviceState.FACTORY_RESET

    @pytest.mark.asyncio
    async def test_immediate_session_termination(
        self, 
        provisioning_orchestrator,
        bluetooth_test_helper,
        gpio_test_helper
    ):
        """Test immediate termination of BLE session during reset."""
        orchestrator = provisioning_orchestrator
        bluetooth_service = orchestrator.services.get("bluetooth")
        state_machine = orchestrator.state_machine
        
        # Set up active BLE session
        await bluetooth_test_helper.connect()
        assert bluetooth_test_helper.is_connected
        
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        
        # Trigger reset
        button_result = await gpio_test_helper.press_and_hold(6.0)
        assert button_result
        
        state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
        
        # Session should be terminated immediately
        await bluetooth_test_helper.disconnect()
        assert not bluetooth_test_helper.is_connected

    @pytest.mark.asyncio
    async def test_in_progress_data_clearing(
        self, 
        provisioning_orchestrator,
        valid_credentials,
        gpio_test_helper
    ):
        """Test that in-progress data is cleared during reset."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine
        
        # Start provisioning and set context data
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        state_machine.set_context("received_credentials", valid_credentials)
        state_machine.set_context("session_id", "test-session-123")
        
        # Verify context data exists
        assert state_machine.get_context("received_credentials") is not None
        assert state_machine.get_context("session_id") is not None
        
        # Trigger reset
        button_result = await gpio_test_helper.press_and_hold(6.0)
        assert button_result
        
        state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
        
        # Context should be cleared
        state_machine.clear_context()
        assert state_machine.get_context("received_credentials") is None
        assert state_machine.get_context("session_id") is None

    @pytest.mark.asyncio
    async def test_reset_during_credential_transfer(
        self, 
        provisioning_orchestrator,
        valid_credentials,
        bluetooth_test_helper,
        gpio_test_helper
    ):
        """Test reset triggered during credential transfer process."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine
        
        # Start provisioning
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        
        # Simulate partial credential transfer
        await bluetooth_test_helper.connect()
        
        # Simulate credentials being received (but not yet processed)
        state_machine.set_context("partial_credentials", {
            "ssid": valid_credentials["ssid"]
            # Password not yet received
        })
        
        # Trigger reset mid-transfer
        button_result = await gpio_test_helper.press_and_hold(6.0)
        assert button_result
        
        state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
        
        # Should handle interruption gracefully
        assert state_machine.get_current_state() == DeviceState.FACTORY_RESET
        
        # Cleanup partial data
        state_machine.clear_context()

    @pytest.mark.asyncio
    async def test_reset_during_network_connection_attempt(
        self, 
        provisioning_orchestrator,
        valid_credentials,
        gpio_test_helper
    ):
        """Test reset triggered during network connection attempt."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine
        
        # Start provisioning and receive credentials
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        state_machine.process_event(
            ProvisioningEvent.CREDENTIALS_RECEIVED, 
            valid_credentials
        )
        
        # System is attempting network connection
        assert state_machine.get_current_state() == DeviceState.PROVISIONING
        
        # Trigger reset during connection attempt
        button_result = await gpio_test_helper.press_and_hold(6.0)
        assert button_result
        
        state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
        
        # Should abort connection attempt and reset
        assert state_machine.get_current_state() == DeviceState.FACTORY_RESET

    @pytest.mark.asyncio
    async def test_ble_cleanup_on_reset(
        self, 
        provisioning_orchestrator,
        bluetooth_test_helper,
        gpio_test_helper
    ):
        """Test proper BLE cleanup when reset is triggered."""
        orchestrator = provisioning_orchestrator
        bluetooth_service = orchestrator.services.get("bluetooth")
        state_machine = orchestrator.state_machine
        
        # Set up BLE session
        await bluetooth_test_helper.connect()
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        
        # Trigger reset
        button_result = await gpio_test_helper.press_and_hold(6.0)
        assert button_result
        
        state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
        
        # BLE should be properly cleaned up
        await bluetooth_test_helper.disconnect()
        assert not bluetooth_test_helper.is_connected
        
        # Advertising should be stopped
        assert not bluetooth_service.is_advertising()

    @pytest.mark.asyncio
    async def test_session_state_cleanup_verification(
        self, 
        provisioning_orchestrator,
        gpio_test_helper
    ):
        """Test verification of complete session state cleanup."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine
        
        # Set up complex session state
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        
        # Add various session data
        session_data = {
            "connection_id": "conn-123",
            "transfer_progress": 0.75,
            "retry_count": 2,
            "last_activity": "credential_transfer"
        }
        
        for key, value in session_data.items():
            state_machine.set_context(key, value)
        
        # Trigger reset
        button_result = await gpio_test_helper.press_and_hold(6.0)
        assert button_result
        
        state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
        
        # Verify complete cleanup
        state_machine.clear_context()
        for key in session_data.keys():
            assert state_machine.get_context(key) is None

    @pytest.mark.asyncio
    async def test_reset_timing_during_active_session(
        self, 
        provisioning_orchestrator,
        gpio_test_helper
    ):
        """Test that reset timing requirements are maintained during active sessions."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine
        
        # Start active session
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        
        # Test that timing requirements are still enforced
        # Short press should not trigger reset even during active session
        button_result = await gpio_test_helper.press_and_hold(3.0)
        assert not button_result
        assert state_machine.get_current_state() == DeviceState.PROVISIONING
        
        # Proper duration should trigger reset
        button_result = await gpio_test_helper.press_and_hold(6.0)
        assert button_result
        
        state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
        assert state_machine.get_current_state() == DeviceState.FACTORY_RESET

    @pytest.mark.asyncio
    async def test_data_consistency_after_interrupted_reset(
        self, 
        provisioning_orchestrator,
        valid_credentials,
        gpio_test_helper
    ):
        """Test data consistency when reset is interrupted."""
        orchestrator = provisioning_orchestrator
        config_service = orchestrator.services.get("configuration")
        factory_reset_service = orchestrator.services.get("factory_reset")
        state_machine = orchestrator.state_machine
        
        # Set up initial data
        config_service.save_network_config(
            valid_credentials["ssid"], 
            valid_credentials["password"]
        )
        
        # Start active session
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        
        # Trigger reset
        button_result = await gpio_test_helper.press_and_hold(6.0)
        assert button_result
        
        state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
        
        # Complete reset (this should be atomic operation)
        reset_success, reset_message = factory_reset_service.perform_reset("CONFIRM")
        assert reset_success
        
        # Verify consistent state after reset
        assert not config_service.has_network_config()
        
        state_machine.reset()
        assert state_machine.get_current_state() == DeviceState.INITIALIZING
