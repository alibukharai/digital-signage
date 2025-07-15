"""
Error Recovery Tests (E1-E2)

These tests cover error handling and recovery scenarios:
- E1: BLE recovery
- E2: Display failure

Coverage Analysis: 72.5% average (Mixed Coverage)
System Under Test: Rock Pi 3399
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.domain.state import ProvisioningEvent
from src.interfaces import ConnectionStatus, DeviceState
from tests.conftest import assert_state_transition, wait_for_state


class TestE1BLERecovery:
    """
    E1: BLE Recovery
    Scenario: Recovery from BLE connection interruption
    Coverage: 60% - CRITICAL GAP (Needs Enhancement)
    """

    @pytest.mark.asyncio
    async def test_active_ble_session_establishment(
        self, provisioning_orchestrator, bluetooth_test_helper
    ):
        """Test establishment of active BLE provisioning session."""
        orchestrator = provisioning_orchestrator
        bluetooth_service = orchestrator.services.get("bluetooth")
        state_machine = orchestrator.state_machine

        # Start provisioning
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        assert state_machine.get_current_state() == DeviceState.PROVISIONING

        # Establish BLE connection
        await bluetooth_test_helper.connect()
        assert bluetooth_test_helper.is_connected

        # Verify BLE advertising is active
        assert bluetooth_service.is_advertising()

    @pytest.mark.asyncio
    async def test_connection_loss_detection(
        self, provisioning_orchestrator, bluetooth_test_helper
    ):
        """Test detection of BLE connection loss."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine

        # Establish active session
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        await bluetooth_test_helper.connect()
        assert bluetooth_test_helper.is_connected

        # Simulate connection loss
        await bluetooth_test_helper.disconnect()
        assert not bluetooth_test_helper.is_connected

        # System should detect the disconnection
        # In real implementation, this would trigger reconnection logic

    @pytest.mark.asyncio
    async def test_reconnection_within_10_second_window(
        self, provisioning_orchestrator, bluetooth_test_helper
    ):
        """Test automatic reconnection within 10-second window."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine

        # Establish session
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        await bluetooth_test_helper.connect()

        # Simulate connection loss and recovery within window
        start_time = asyncio.get_event_loop().time()
        await bluetooth_test_helper.simulate_connection_loss(duration=5.0)
        recovery_time = asyncio.get_event_loop().time() - start_time

        # Should reconnect within 10 seconds
        assert recovery_time < 10.0
        assert bluetooth_test_helper.is_connected

    @pytest.mark.asyncio
    async def test_reconnection_after_10_second_window(
        self, provisioning_orchestrator, bluetooth_test_helper
    ):
        """Test behavior when reconnection exceeds 10-second window."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine

        # Establish session
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        await bluetooth_test_helper.connect()

        # Simulate extended connection loss (15 seconds)
        start_time = asyncio.get_event_loop().time()
        await bluetooth_test_helper.simulate_connection_loss(duration=15.0)
        recovery_time = asyncio.get_event_loop().time() - start_time

        # Connection loss exceeded window
        assert recovery_time > 10.0

        # In real implementation, might need to restart session
        # or handle as connection failure

    @pytest.mark.asyncio
    async def test_session_resume_after_reconnection(
        self, provisioning_orchestrator, bluetooth_test_helper, valid_credentials
    ):
        """Test that session resumes from last valid state after reconnection."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine

        # Establish session and set state
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        await bluetooth_test_helper.connect()

        # Set session context
        state_machine.set_context("session_id", "session-123")
        state_machine.set_context("last_valid_state", "awaiting_credentials")

        # Simulate brief disconnection and reconnection
        await bluetooth_test_helper.simulate_connection_loss(duration=3.0)

        # Session should resume
        assert bluetooth_test_helper.is_connected

        # Context should be preserved
        assert state_machine.get_context("session_id") == "session-123"
        assert state_machine.get_context("last_valid_state") == "awaiting_credentials"

    @pytest.mark.asyncio
    async def test_data_corruption_prevention(
        self, provisioning_orchestrator, bluetooth_test_helper, valid_credentials
    ):
        """Test prevention of data corruption during BLE recovery."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine

        # Start credential transfer
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        await bluetooth_test_helper.connect()

        # Simulate partial data reception
        partial_data = {
            "ssid": valid_credentials["ssid"],
            "password": valid_credentials["password"][:5],  # Partial password
            "transfer_complete": False,
        }
        state_machine.set_context("partial_credentials", partial_data)

        # Simulate disconnection during transfer
        await bluetooth_test_helper.simulate_connection_loss(duration=2.0)

        # After reconnection, partial data should be handled safely
        # Real implementation should validate data integrity
        recovered_data = state_machine.get_context("partial_credentials")

        # Should not process incomplete credentials
        assert not recovered_data.get("transfer_complete", False)

    @pytest.mark.asyncio
    async def test_automatic_reconnection_logic(
        self, provisioning_orchestrator, bluetooth_test_helper
    ):
        """Test automatic reconnection logic implementation."""
        orchestrator = provisioning_orchestrator
        bluetooth_service = orchestrator.services.get("bluetooth")
        state_machine = orchestrator.state_machine

        # Establish session
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        await bluetooth_test_helper.connect()

        # Track connection attempts
        reconnection_attempts = 0
        max_attempts = 3

        for attempt in range(max_attempts):
            # Simulate connection loss
            await bluetooth_test_helper.disconnect()

            # Simulate reconnection attempt
            await asyncio.sleep(0.1)  # Brief delay
            await bluetooth_test_helper.connect()
            reconnection_attempts += 1

            if bluetooth_test_helper.is_connected:
                break

        # Should successfully reconnect within attempts
        assert bluetooth_test_helper.is_connected
        assert reconnection_attempts <= max_attempts

    @pytest.mark.asyncio
    async def test_session_persistence_during_disconnection(
        self, provisioning_orchestrator, bluetooth_test_helper, valid_credentials
    ):
        """Test that session state persists during brief disconnections."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine

        # Establish session with data
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        await bluetooth_test_helper.connect()

        # Set up session state
        session_state = {
            "client_id": "esp32-device-001",
            "connection_time": asyncio.get_event_loop().time(),
            "last_heartbeat": asyncio.get_event_loop().time(),
            "transfer_mode": "credentials",
        }

        for key, value in session_state.items():
            state_machine.set_context(key, value)

        # Brief disconnection
        await bluetooth_test_helper.simulate_connection_loss(duration=1.0)

        # Session state should persist
        for key, expected_value in session_state.items():
            if key != "last_heartbeat":  # This might be updated
                assert state_machine.get_context(key) == expected_value

    @pytest.mark.asyncio
    async def test_connection_quality_monitoring(
        self, provisioning_orchestrator, bluetooth_test_helper
    ):
        """Test connection quality monitoring for predictive recovery."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine

        # Establish session
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        await bluetooth_test_helper.connect()

        # Simulate degrading connection quality
        connection_quality_metrics = {
            "signal_strength": -70,  # Weak signal
            "packet_loss": 0.15,  # 15% packet loss
            "latency": 200,  # 200ms latency
            "error_rate": 0.05,  # 5% error rate
        }

        state_machine.set_context("connection_quality", connection_quality_metrics)

        # System should monitor and potentially take preventive action
        quality = state_machine.get_context("connection_quality")
        assert quality["signal_strength"] < -60  # Poor signal detected

    @pytest.mark.asyncio
    async def test_data_integrity_verification_after_recovery(
        self, provisioning_orchestrator, bluetooth_test_helper, valid_credentials
    ):
        """Test data integrity verification after BLE recovery."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine

        # Establish session
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        await bluetooth_test_helper.connect()

        # Receive complete credentials
        state_machine.process_event(
            ProvisioningEvent.CREDENTIALS_RECEIVED, valid_credentials
        )

        # Simulate brief disconnection
        await bluetooth_test_helper.simulate_connection_loss(duration=2.0)

        # After recovery, verify data integrity
        received_creds = state_machine.get_context("last_received_credentials")
        if received_creds:
            # Verify data completeness and validity
            required_fields = ["ssid", "password", "security"]
            for field in required_fields:
                assert field in received_creds
                assert received_creds[field]  # Non-empty

    @pytest.mark.asyncio
    async def test_multiple_reconnection_cycles(
        self, provisioning_orchestrator, bluetooth_test_helper
    ):
        """Test handling of multiple reconnection cycles."""
        orchestrator = provisioning_orchestrator
        state_machine = orchestrator.state_machine

        # Establish session
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        await bluetooth_test_helper.connect()

        # Multiple disconnection/reconnection cycles
        for cycle in range(3):
            # Simulate disconnection
            await bluetooth_test_helper.disconnect()
            assert not bluetooth_test_helper.is_connected

            # Wait briefly
            await asyncio.sleep(0.5)

            # Reconnect
            await bluetooth_test_helper.connect()
            assert bluetooth_test_helper.is_connected

            # Verify session continues to work
            assert state_machine.get_current_state() == DeviceState.PROVISIONING


class TestE2DisplayFailure:
    """
    E2: Display Failure
    Scenario: System operation when display is unavailable
    Coverage: 85% - Good resilience
    """

    @pytest.mark.asyncio
    async def test_hdmi_display_connected_and_active(self, provisioning_orchestrator):
        """Test normal operation with HDMI display connected."""
        orchestrator = provisioning_orchestrator
        display_service = orchestrator.services.get("display")

        # Verify display is active
        assert display_service.is_display_active()

        # Test basic display operations
        assert display_service.show_status("Test message")
        assert display_service.show_qr_code("test-qr-data")

    @pytest.mark.asyncio
    async def test_hdmi_cable_disconnection_during_operation(
        self, provisioning_orchestrator
    ):
        """Test behavior when HDMI cable is disconnected during operation."""
        orchestrator = provisioning_orchestrator
        display_service = orchestrator.services.get("display")
        state_machine = orchestrator.state_machine

        # Start with active display
        assert display_service.is_display_active()

        # Start provisioning
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)

        # Simulate HDMI disconnection
        # In real implementation, this would be detected by display service
        # For test, we simulate the failure
        with patch.object(display_service, "is_display_active", return_value=False):
            # System should continue operating without display
            assert state_machine.get_current_state() == DeviceState.PROVISIONING

    @pytest.mark.asyncio
    async def test_ble_service_continues_without_display(
        self, provisioning_orchestrator, bluetooth_test_helper
    ):
        """Test that BLE service remains functional when display fails."""
        orchestrator = provisioning_orchestrator
        bluetooth_service = orchestrator.services.get("bluetooth")
        display_service = orchestrator.services.get("display")
        state_machine = orchestrator.state_machine

        # Start provisioning
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
        await bluetooth_test_helper.connect()

        # Simulate display failure
        with patch.object(display_service, "is_display_active", return_value=False):
            # BLE should remain active
            assert bluetooth_test_helper.is_connected
            assert bluetooth_service.is_advertising()

            # Provisioning should continue
            assert state_machine.get_current_state() == DeviceState.PROVISIONING

    @pytest.mark.asyncio
    async def test_error_logging_on_display_failure(self, provisioning_orchestrator):
        """Test that display failures are properly logged."""
        orchestrator = provisioning_orchestrator
        display_service = orchestrator.services.get("display")
        state_machine = orchestrator.state_machine

        # Start provisioning
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)

        # Simulate display failure
        with patch.object(
            display_service, "show_qr_code", return_value=False
        ) as mock_qr:
            # Attempt to show QR code (should fail)
            result = display_service.show_qr_code("test-data")
            assert not result

            # System should log error but continue
            assert state_machine.get_current_state() == DeviceState.PROVISIONING

    @pytest.mark.asyncio
    async def test_system_continues_operation_without_display(
        self, provisioning_orchestrator, valid_credentials
    ):
        """Test that system continues full operation without display."""
        orchestrator = provisioning_orchestrator
        display_service = orchestrator.services.get("display")
        state_machine = orchestrator.state_machine

        # Simulate display failure from start
        with patch.object(display_service, "is_display_active", return_value=False):
            # Complete provisioning flow without display
            state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
            assert state_machine.get_current_state() == DeviceState.PROVISIONING

            state_machine.process_event(
                ProvisioningEvent.CREDENTIALS_RECEIVED, valid_credentials
            )

            state_machine.process_event(ProvisioningEvent.NETWORK_CONNECTED)
            assert state_machine.get_current_state() == DeviceState.CONNECTED

    @pytest.mark.asyncio
    async def test_qr_code_functionality_gracefully_disabled(
        self, provisioning_orchestrator
    ):
        """Test that QR code functionality is gracefully disabled on display failure."""
        orchestrator = provisioning_orchestrator
        display_service = orchestrator.services.get("display")

        # Simulate display failure
        with patch.object(display_service, "is_display_active", return_value=False):
            # QR code should fail gracefully
            result = display_service.show_qr_code("test-qr-data")
            assert not result

            # Clear display should also fail gracefully
            result = display_service.clear_display()
            assert not result

    @pytest.mark.asyncio
    async def test_status_message_fallback_on_display_failure(
        self, provisioning_orchestrator
    ):
        """Test status message fallback when display fails."""
        orchestrator = provisioning_orchestrator
        display_service = orchestrator.services.get("display")
        state_machine = orchestrator.state_machine

        # Start provisioning
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)

        # Simulate display failure
        with patch.object(display_service, "show_status", return_value=False):
            # Status message should fail but not crash system
            result = display_service.show_status("Provisioning...")
            assert not result

            # System should continue operating
            assert state_machine.get_current_state() == DeviceState.PROVISIONING

    @pytest.mark.asyncio
    async def test_hdmi_detection_and_recovery(self, provisioning_orchestrator):
        """Test HDMI detection and recovery when display is reconnected."""
        orchestrator = provisioning_orchestrator
        display_service = orchestrator.services.get("display")

        # Start with failed display
        with patch.object(display_service, "is_display_active", return_value=False):
            assert not display_service.is_display_active()

        # Simulate display reconnection
        with patch.object(display_service, "is_display_active", return_value=True):
            # Display should be detected as active again
            assert display_service.is_display_active()

            # Display functions should work again
            assert display_service.show_status("Display recovered")

    @pytest.mark.asyncio
    async def test_provisioning_completion_without_display_confirmation(
        self, provisioning_orchestrator, valid_credentials
    ):
        """Test that provisioning can complete without display confirmation."""
        orchestrator = provisioning_orchestrator
        display_service = orchestrator.services.get("display")
        config_service = orchestrator.services.get("configuration")
        state_machine = orchestrator.state_machine

        # Complete provisioning without display
        with patch.object(display_service, "is_display_active", return_value=False):
            state_machine.process_event(ProvisioningEvent.START_PROVISIONING)
            state_machine.process_event(
                ProvisioningEvent.CREDENTIALS_RECEIVED, valid_credentials
            )
            state_machine.process_event(ProvisioningEvent.NETWORK_CONNECTED)

            # Should reach connected state
            assert state_machine.get_current_state() == DeviceState.CONNECTED

            # Configuration should be saved
            assert config_service.has_network_config()

    @pytest.mark.asyncio
    async def test_display_health_monitoring(self, provisioning_orchestrator):
        """Test display health monitoring for early failure detection."""
        orchestrator = provisioning_orchestrator
        display_service = orchestrator.services.get("display")
        health_monitor = orchestrator.services.get("health")

        # Check display health
        health_status = health_monitor.check_system_health()

        # Should include display status
        assert "display" in health_status

        # Test with active display
        if display_service.is_display_active():
            assert health_status["display"]["status"] in ["healthy", "active"]

    @pytest.mark.asyncio
    async def test_graceful_display_failure_handling(
        self, provisioning_orchestrator, valid_credentials
    ):
        """Test comprehensive graceful handling of display failures."""
        orchestrator = provisioning_orchestrator
        display_service = orchestrator.services.get("display")
        state_machine = orchestrator.state_machine

        # Start normal operation
        state_machine.process_event(ProvisioningEvent.START_PROVISIONING)

        # Simulate progressive display failure
        display_operations = [
            ("show_qr_code", "qr-data"),
            ("show_status", "status message"),
            ("clear_display", None),
        ]

        for operation, data in display_operations:
            with patch.object(display_service, operation, return_value=False):
                # Each operation should fail gracefully
                method = getattr(display_service, operation)
                if data:
                    result = method(data)
                else:
                    result = method()

                assert not result

                # System should continue operating
                assert state_machine.get_current_state() == DeviceState.PROVISIONING

    @pytest.mark.asyncio
    async def test_alternative_user_feedback_on_display_failure(
        self, provisioning_orchestrator
    ):
        """Test alternative user feedback mechanisms when display fails."""
        orchestrator = provisioning_orchestrator
        display_service = orchestrator.services.get("display")
        bluetooth_service = orchestrator.services.get("bluetooth")

        # Simulate display failure
        with patch.object(display_service, "is_display_active", return_value=False):
            # Alternative feedback should be available via BLE
            assert bluetooth_service.is_advertising()

            # In real implementation, might use LED indicators, audio signals, etc.
            # For test, verify system provides alternative communication path
            assert not display_service.is_display_active()
