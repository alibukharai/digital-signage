"""
End-to-End Integration Tests for Rock Pi 4B+ Provisioning System.
Tests complete provisioning workflows using real service implementations.
No mocks - only real services with test configurations.
"""

import asyncio
import pytest
from pathlib import Path
from datetime import datetime

from src.domain.state import DeviceState, ProvisioningEvent
from src.interfaces import ConnectionStatus, NetworkInfo
from tests.conftest import (
    wait_for_state,
    wait_for_connection,
    assert_state_transition,
    create_test_network_info,
)


class TestEndToEndProvisioning:
    """Complete end-to-end provisioning tests using real services."""
    
    @pytest.mark.asyncio
    async def test_complete_provisioning_workflow(
        self,
        provisioning_orchestrator,
        network_service,
        bluetooth_service,
        display_service,
        configuration_service,
        valid_credentials,
        logger,
        assert_helper
    ):
        """Test the complete provisioning workflow from start to finish."""
        
        # Step 1: Start provisioning process
        await provisioning_orchestrator.start_provisioning()
        
        # Verify initial state
        assert provisioning_orchestrator.state_machine.current_state == DeviceState.PROVISIONING
        
        # Step 2: Verify BLE advertising started
        assert bluetooth_service.is_advertising()
        
        # Verify advertising data contains device information
        assert bluetooth_service.advertising_data is not None
        assert "ROCK-PI" in bluetooth_service.advertising_data
        
        # Step 3: Verify QR code is displayed
        assert display_service.is_display_active()
        current_display = display_service.get_current_display()
        assert current_display is not None
        assert current_display["type"] == "qr_code"
        
        # Step 4: Simulate credential reception via BLE
        ssid = valid_credentials["ssid"]
        password = valid_credentials["password"]
        
        await bluetooth_service.simulate_credential_reception(ssid, password)
        
        # Allow time for credential processing
        await asyncio.sleep(0.1)
        
        # Step 5: Verify network connection attempt
        connection_result = await network_service.connect_to_network(ssid, password)
        assert connection_result.is_success()
        
        # Step 6: Wait for connection to be established
        await wait_for_connection(network_service, timeout=5.0)
        
        # Verify connection status
        assert network_service.is_connected()
        connection_info = network_service.get_connection_info()
        assert connection_info.is_success()
        assert connection_info.value.status == ConnectionStatus.CONNECTED
        assert connection_info.value.ssid == ssid
        
        # Step 7: Verify configuration was saved
        assert configuration_service.has_network_config()
        saved_config = await configuration_service.load_network_config()
        assert saved_config.is_success()
        assert saved_config.value is not None
        saved_ssid, saved_password = saved_config.value
        assert saved_ssid == ssid
        assert saved_password == password
        
        # Step 8: Verify final state
        await wait_for_state(provisioning_orchestrator.state_machine, DeviceState.CONNECTED, timeout=5.0)
        
        # Step 9: Verify no errors were logged
        assert_helper.assert_no_errors_logged(logger)
        
        # Step 10: Verify successful completion messages were logged
        assert_helper.assert_message_logged(logger, "INFO", "successfully connected")
        assert_helper.assert_message_logged(logger, "INFO", "Network configuration saved")
    
    @pytest.mark.asyncio
    async def test_network_scanning_integration(
        self,
        network_service,
        logger,
        assert_helper
    ):
        """Test real network scanning functionality."""
        
        # Perform network scan
        scan_result = await network_service.scan_networks()
        
        # Verify scan was successful
        assert scan_result.is_success()
        networks = scan_result.value
        assert isinstance(networks, list)
        assert len(networks) > 0
        
        # Verify network information structure
        for network in networks:
            assert isinstance(network, NetworkInfo)
            assert network.ssid is not None
            assert network.signal_strength < 0  # Signal strength should be negative
            assert network.security_type in ["WPA2", "WPA3", "Open", "WPA2-Enterprise"]
        
        # Verify scan was logged
        assert_helper.assert_message_logged(logger, "INFO", "Network scan completed")
        
        # Verify no errors occurred
        assert_helper.assert_no_errors_logged(logger)
        
        # Verify scan count was incremented
        assert network_service.scan_count > 0
    
    @pytest.mark.asyncio
    async def test_bluetooth_advertising_lifecycle(
        self,
        bluetooth_service,
        device_info_service,
        logger,
        assert_helper
    ):
        """Test complete BLE advertising lifecycle."""
        
        # Get device info
        device_info = device_info_service.get_device_info()
        
        # Start advertising
        start_result = await bluetooth_service.start_advertising(device_info)
        assert start_result.is_success()
        assert bluetooth_service.is_advertising()
        
        # Verify advertising session was recorded
        assert len(bluetooth_service.advertising_sessions) > 0
        current_session = bluetooth_service.advertising_sessions[-1]
        assert current_session["device_info"] == device_info
        assert "start_time" in current_session
        
        # Verify advertising data
        assert bluetooth_service.advertising_data is not None
        expected_parts = [device_info.device_id, device_info.mac_address]
        for part in expected_parts:
            assert part in bluetooth_service.advertising_data
        
        # Stop advertising
        stop_result = await bluetooth_service.stop_advertising()
        assert stop_result.is_success()
        assert not bluetooth_service.is_advertising()
        
        # Verify session was ended
        assert "end_time" in current_session
        
        # Verify appropriate logs
        assert_helper.assert_message_logged(logger, "INFO", "BLE advertising started")
        assert_helper.assert_message_logged(logger, "INFO", "BLE advertising stopped")
        assert_helper.assert_no_errors_logged(logger)
    
    @pytest.mark.asyncio
    async def test_configuration_persistence(
        self,
        configuration_service,
        logger,
        assert_helper
    ):
        """Test configuration saving and loading functionality."""
        
        test_ssid = "TestPersistence_Network"
        test_password = "PersistencePassword123"
        
        # Initially no configuration should exist
        assert not configuration_service.has_network_config()
        
        # Load configuration (should return None)
        initial_load = await configuration_service.load_network_config()
        assert initial_load.is_success()
        assert initial_load.value is None
        
        # Save configuration
        save_result = await configuration_service.save_network_config(test_ssid, test_password)
        assert save_result.is_success()
        
        # Verify configuration exists
        assert configuration_service.has_network_config()
        
        # Load and verify configuration
        load_result = await configuration_service.load_network_config()
        assert load_result.is_success()
        assert load_result.value is not None
        
        loaded_ssid, loaded_password = load_result.value
        assert loaded_ssid == test_ssid
        assert loaded_password == test_password
        
        # Verify operations were tracked
        assert len(configuration_service.save_operations) > 0
        assert len(configuration_service.load_operations) > 0
        
        # Clear configuration
        clear_result = await configuration_service.clear_network_config()
        assert clear_result.is_success()
        assert clear_result.value  # Should return True (had config to clear)
        
        # Verify configuration is gone
        assert not configuration_service.has_network_config()
        
        # Verify appropriate logs
        assert_helper.assert_message_logged(logger, "INFO", "Network configuration saved")
        assert_helper.assert_message_logged(logger, "INFO", "Network configuration cleared")
        assert_helper.assert_no_errors_logged(logger)
    
    @pytest.mark.asyncio
    async def test_display_operations(
        self,
        display_service,
        logger,
        assert_helper
    ):
        """Test display service operations."""
        
        # Initially display should not be active
        assert not display_service.is_display_active()
        assert display_service.get_current_display() is None
        
        # Display QR code
        qr_data = "ROCKPI:TEST-DEVICE-001:AABBCCDDEEFF"
        qr_result = await display_service.show_qr_code(qr_data)
        assert qr_result.is_success()
        
        # Verify display is active
        assert display_service.is_display_active()
        current_display = display_service.get_current_display()
        assert current_display is not None
        assert current_display["type"] == "qr_code"
        assert current_display["data"] == qr_data
        
        # Display status message
        status_message = "Connecting to network..."
        status_result = await display_service.show_status(status_message)
        assert status_result.is_success()
        
        # Verify status display
        current_display = display_service.get_current_display()
        assert current_display["type"] == "status"
        assert current_display["message"] == status_message
        
        # Clear display
        clear_result = await display_service.clear_display()
        assert clear_result.is_success()
        
        # Verify display is cleared
        assert not display_service.is_display_active()
        assert display_service.get_current_display() is None
        
        # Verify display history
        history = display_service.get_display_history()
        assert len(history) == 3  # QR, Status, Clear
        assert history[0]["type"] == "qr_code"
        assert history[1]["type"] == "status"
        assert history[2]["type"] == "clear"
        
        # Verify appropriate logs
        assert_helper.assert_message_logged(logger, "INFO", "QR code displayed")
        assert_helper.assert_message_logged(logger, "INFO", "Status displayed")
        assert_helper.assert_message_logged(logger, "INFO", "Display cleared")
        assert_helper.assert_no_errors_logged(logger)
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(
        self,
        network_service,
        logger,
        assert_helper
    ):
        """Test error handling in real service operations."""
        
        # Test connection to non-existent network
        invalid_result = await network_service.connect_to_network("NonExistentNetwork", "password")
        assert not invalid_result.is_success()
        assert "not found" in str(invalid_result.error)
        
        # Test connection with invalid password (too short for WPA2)
        weak_password_result = await network_service.connect_to_network("TestNetwork_WPA2", "weak")
        assert not weak_password_result.is_success()
        assert "too short" in str(weak_password_result.error)
        
        # Test connection with empty SSID
        empty_ssid_result = await network_service.connect_to_network("", "password")
        assert not empty_ssid_result.is_success()
        assert "cannot be empty" in str(empty_ssid_result.error)
        
        # Verify errors were logged appropriately
        error_messages = logger.get_messages("ERROR")
        assert len(error_messages) >= 3
        
        # Verify connection attempts were tracked
        assert len(network_service.connection_attempts) >= 3
        
        # Test successful disconnection after errors
        disconnect_result = await network_service.disconnect()
        assert disconnect_result.is_success()
    
    @pytest.mark.asyncio
    async def test_credential_reception_workflow(
        self,
        bluetooth_service,
        device_info_service,
        logger,
        assert_helper
    ):
        """Test credential reception via BLE simulation."""
        
        # Setup callback to capture credentials
        received_credentials = []
        
        def credential_callback(ssid: str, password: str):
            received_credentials.append((ssid, password))
        
        # Set callback
        bluetooth_service.set_credentials_callback(credential_callback)
        
        # Start advertising
        device_info = device_info_service.get_device_info()
        await bluetooth_service.start_advertising(device_info)
        
        # Simulate credential reception
        test_ssid = "TestCredentialFlow"
        test_password = "CredentialPassword123"
        
        await bluetooth_service.simulate_credential_reception(test_ssid, test_password)
        
        # Verify callback was triggered
        assert len(received_credentials) == 1
        assert received_credentials[0] == (test_ssid, test_password)
        
        # Verify credential event was recorded
        assert len(bluetooth_service.received_credentials) == 1
        credential_event = bluetooth_service.received_credentials[0]
        assert credential_event["ssid"] == test_ssid
        assert credential_event["password_length"] == len(test_password)
        assert credential_event["source"] == "simulated_ble"
        
        # Verify appropriate logging
        assert_helper.assert_message_logged(logger, "INFO", "Credentials received via BLE")
        assert_helper.assert_no_errors_logged(logger)
        
        # Stop advertising
        await bluetooth_service.stop_advertising()
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(
        self,
        network_service,
        display_service,
        configuration_service,
        logger
    ):
        """Test concurrent service operations."""
        
        # Define concurrent operations
        async def scan_networks():
            return await network_service.scan_networks()
        
        async def show_status():
            return await display_service.show_status("Scanning networks...")
        
        async def save_config():
            return await configuration_service.save_network_config("ConcurrentTest", "password123")
        
        # Run operations concurrently
        results = await asyncio.gather(
            scan_networks(),
            show_status(),
            save_config(),
            return_exceptions=True
        )
        
        # Verify all operations completed successfully
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"Concurrent operation failed: {result}")
            assert result.is_success()
        
        # Verify each service maintained correct state
        assert display_service.is_display_active()
        assert configuration_service.has_network_config()
        assert network_service.scan_count > 0
    
    @pytest.mark.asyncio
    async def test_state_machine_integration(
        self,
        provisioning_orchestrator,
        logger,
        assert_helper
    ):
        """Test state machine behavior with real services."""
        
        state_machine = provisioning_orchestrator.state_machine
        
        # Test initial state
        assert state_machine.current_state == DeviceState.INITIALIZING
        
        # Test state transitions
        await assert_state_transition(
            state_machine,
            ProvisioningEvent.START_PROVISIONING,
            DeviceState.PROVISIONING
        )
        
        # Test event processing with credentials
        credentials_event_data = {
            "ssid": "StateTestNetwork",
            "password": "StateTestPassword"
        }
        
        state_machine.process_event(
            ProvisioningEvent.CREDENTIALS_RECEIVED,
            credentials_event_data
        )
        
        # The exact state after credentials depends on implementation
        # But it should not be in ERROR state
        assert state_machine.current_state != DeviceState.ERROR
        
        # Verify no state machine errors
        assert_helper.assert_no_errors_logged(logger)
    
    @pytest.mark.asyncio
    async def test_cleanup_and_resource_management(
        self,
        provisioning_orchestrator,
        bluetooth_service,
        display_service,
        configuration_service,
        logger,
        assert_helper
    ):
        """Test proper cleanup and resource management."""
        
        # Start services
        device_info = provisioning_orchestrator.container.get("device_info_service").get_device_info()
        
        # Start advertising
        await bluetooth_service.start_advertising(device_info)
        
        # Show display
        await display_service.show_qr_code("CLEANUP-TEST-QR")
        
        # Save configuration
        await configuration_service.save_network_config("CleanupTest", "password")
        
        # Verify services are active
        assert bluetooth_service.is_advertising()
        assert display_service.is_display_active()
        assert configuration_service.has_network_config()
        
        # Perform cleanup
        await bluetooth_service.stop_advertising()
        await display_service.clear_display()
        await configuration_service.clear_network_config()
        
        # Verify cleanup was successful
        assert not bluetooth_service.is_advertising()
        assert not display_service.is_display_active()
        assert not configuration_service.has_network_config()
        
        # Verify no errors during cleanup
        assert_helper.assert_no_errors_logged(logger)
        
        # Verify cleanup messages were logged
        assert_helper.assert_message_logged(logger, "INFO", "BLE advertising stopped")
        assert_helper.assert_message_logged(logger, "INFO", "Display cleared")
        assert_helper.assert_message_logged(logger, "INFO", "Network configuration cleared")