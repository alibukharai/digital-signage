"""
Integration tests for QR code display and serial output functionality
"""

import asyncio
import pytest
import json
import sys
from io import StringIO
from contextlib import redirect_stdout

from src.infrastructure.device.info_provider import DeviceInfoProvider
from src.infrastructure.display.qr_generator import QRCodeGenerator
from src.infrastructure.testing.hardware_adapters import TestServiceFactory


class TestQRCodeIntegration:
    """Integration tests for QR code generation, display, and serial output"""

    @pytest.fixture
    def test_factory(self):
        """Create test service factory"""
        factory = TestServiceFactory()
        yield factory
        factory.cleanup()

    @pytest.fixture
    def device_info_provider(self, test_factory):
        """Create device info provider with test adapter"""
        with test_factory.hardware_adapter.patch_file_system():
            provider = DeviceInfoProvider()
            return provider

    @pytest.fixture
    def qr_generator(self):
        """Create QR code generator"""
        return QRCodeGenerator()

    def test_device_provisioning_data_generation(self, device_info_provider):
        """Test generation of device provisioning data for QR codes"""
        # Get device info
        device_info = device_info_provider.get_device_info()
        
        # Verify device info is collected
        assert device_info.device_id is not None
        assert device_info.mac_address is not None
        assert device_info.hardware_version is not None
        
        # Get provisioning code
        provisioning_code = device_info_provider.get_provisioning_code()
        assert provisioning_code is not None
        assert ":" in provisioning_code  # Should have format PREFIX:ID:MAC
        
        # Test new serial output method
        serial_data = device_info_provider.get_provisioning_data_for_serial()
        assert isinstance(serial_data, dict)
        assert "device_id" in serial_data
        assert "mac_address" in serial_data
        assert "provisioning_code" in serial_data
        assert "hardware_version" in serial_data
        assert "soc_name" in serial_data
        assert "capabilities" in serial_data

    def test_qr_code_generation(self, qr_generator):
        """Test QR code generation with both image and text output"""
        test_data = "ROCKPI4B+:a1b2c3d4:aabbccddeeff"
        
        # Generate QR code data
        result = qr_generator.generate_qr_code_data(test_data)
        assert result.is_success()
        
        qr_info = result.value
        assert qr_info["data"] == test_data
        assert qr_info["data_length"] == len(test_data)
        assert "text_representation" in qr_info
        assert "image_available" in qr_info

    def test_qr_code_serial_output_json(self, qr_generator):
        """Test QR code serial output in JSON format"""
        test_data = "ROCKPI4B+:a1b2c3d4:aabbccddeeff"
        
        # Capture stdout
        captured_output = StringIO()
        
        with redirect_stdout(captured_output):
            result = qr_generator.output_qr_to_serial(test_data, "json")
            assert result.is_success()
        
        output = captured_output.getvalue()
        assert "==== QR_CODE_JSON_START ====" in output
        assert "==== QR_CODE_JSON_END ====" in output
        
        # Extract JSON content
        lines = output.split('\n')
        json_start = None
        json_end = None
        
        for i, line in enumerate(lines):
            if "QR_CODE_JSON_START" in line:
                json_start = i + 1
            elif "QR_CODE_JSON_END" in line:
                json_end = i
                break
        
        assert json_start is not None
        assert json_end is not None
        
        json_content = '\n'.join(lines[json_start:json_end])
        parsed_data = json.loads(json_content)
        
        assert "qr_code_info" in parsed_data
        qr_info = parsed_data["qr_code_info"]
        assert qr_info["data"] == test_data
        assert qr_info["data_length"] == len(test_data)

    def test_qr_code_serial_output_text(self, qr_generator):
        """Test QR code serial output in text format"""
        test_data = "ROCKPI4B+:a1b2c3d4:aabbccddeeff"
        
        captured_output = StringIO()
        
        with redirect_stdout(captured_output):
            result = qr_generator.output_qr_to_serial(test_data, "text")
            assert result.is_success()
        
        output = captured_output.getvalue()
        assert "==== QR_CODE_TEXT_START ====" in output
        assert "==== QR_CODE_TEXT_END ====" in output
        assert f"QR Code Data: {test_data}" in output
        assert f"Data Length: {len(test_data)} characters" in output

    def test_qr_code_serial_output_ascii(self, qr_generator):
        """Test QR code serial output in ASCII format"""
        test_data = "ROCKPI4B+:a1b2c3d4:aabbccddeeff"
        
        captured_output = StringIO()
        
        with redirect_stdout(captured_output):
            result = qr_generator.output_qr_to_serial(test_data, "ascii")
            assert result.is_success()
        
        output = captured_output.getvalue()
        assert "==== QR_CODE_ASCII_START ====" in output
        assert "==== QR_CODE_ASCII_END ====" in output
        assert f"Data: {test_data}" in output
        assert "ASCII QR Code:" in output

    def test_end_to_end_provisioning_flow(self, test_factory, device_info_provider, qr_generator):
        """Test complete end-to-end provisioning flow with QR code and serial output"""
        # Step 1: Get device provisioning data
        provisioning_code = device_info_provider.get_provisioning_code()
        assert provisioning_code is not None
        
        # Step 2: Generate QR code
        qr_result = qr_generator.generate_qr_code_data(provisioning_code)
        assert qr_result.is_success()
        
        # Step 3: Test serial output for monitoring
        captured_output = StringIO()
        with redirect_stdout(captured_output):
            serial_result = qr_generator.output_qr_to_serial(provisioning_code, "json")
            assert serial_result.is_success()
        
        # Verify serial output contains expected data
        output = captured_output.getvalue()
        assert provisioning_code in output
        
        # Step 4: Verify device info is available for tests
        serial_data = device_info_provider.get_provisioning_data_for_serial()
        assert serial_data["provisioning_code"] == provisioning_code

    def test_qr_code_caching(self, qr_generator):
        """Test QR code data caching functionality"""
        test_data = "ROCKPI4B+:cached:test"
        
        # Generate first time
        result1 = qr_generator.generate_qr_code_data(test_data)
        assert result1.is_success()
        
        # Check cached data
        cached_data = qr_generator.get_qr_data()
        assert cached_data == test_data
        
        # Check cached image
        cached_image = qr_generator.get_qr_image()
        assert cached_image is not None  # Should have cached image

    def test_qr_code_fallback_without_libraries(self, qr_generator):
        """Test QR code generation fallback when libraries are not available"""
        # Temporarily disable QR libraries
        original_qr_available = qr_generator.__class__.__module__
        
        # Mock the QR_AVAILABLE constant to False
        import src.infrastructure.display.qr_generator as qr_module
        original_available = qr_module.QR_AVAILABLE
        qr_module.QR_AVAILABLE = False
        
        try:
            test_data = "ROCKPI4B+:fallback:test"
            result = qr_generator.generate_qr_code_data(test_data)
            assert result.is_success()
            
            qr_info = result.value
            assert qr_info["image_available"] is False
            assert "text_representation" in qr_info
            assert qr_info["data"] == test_data
            
        finally:
            # Restore original state
            qr_module.QR_AVAILABLE = original_available

    def test_invalid_output_format(self, qr_generator):
        """Test error handling for invalid output format"""
        test_data = "ROCKPI4B+:test:data"
        
        result = qr_generator.output_qr_to_serial(test_data, "invalid_format")
        assert not result.is_success()
        assert "Unsupported output format" in str(result.error)

    def test_display_image_creation(self, qr_generator):
        """Test display image creation with different resolutions"""
        test_data = "ROCKPI4B+:display:test"
        
        # Generate QR code first
        qr_result = qr_generator.generate_qr_code_data(test_data)
        assert qr_result.is_success()
        
        qr_image = qr_generator.get_qr_image()
        if qr_image:  # Only test if QR libraries are available
            # Test 1080p display
            display_img_1080p = qr_generator.create_display_image(
                qr_image, test_data, 1920, 1080
            )
            assert display_img_1080p.size == (1920, 1080)
            
            # Test 4K display
            display_img_4k = qr_generator.create_display_image(
                qr_image, test_data, 3840, 2160
            )
            assert display_img_4k.size == (3840, 2160)

    def test_concurrent_qr_generation(self, qr_generator):
        """Test concurrent QR code generation for stress testing"""
        async def generate_qr(data):
            return qr_generator.generate_qr_code_data(data)
        
        async def test_concurrent():
            tasks = []
            for i in range(10):
                test_data = f"ROCKPI4B+:concurrent:{i}"
                tasks.append(generate_qr(test_data))
            
            results = await asyncio.gather(*tasks)
            
            # All should succeed
            for result in results:
                assert result.is_success()
            
            # Each should have unique data
            data_values = [result.value["data"] for result in results]
            assert len(set(data_values)) == 10  # All unique
        
        # Run the async test
        asyncio.run(test_concurrent())


class TestRealDisplayIntegration:
    """Integration tests for real display service with QR code enhancement"""
    
    @pytest.fixture
    def test_factory(self):
        """Create test service factory"""
        factory = TestServiceFactory()
        yield factory
        factory.cleanup()

    def test_display_service_qr_output(self, test_factory):
        """Test display service with QR code serial output"""
        display_adapter = test_factory.display_adapter
        
        test_data = "ROCKPI4B+:display:integration"
        
        # Display QR code
        result = display_adapter.display_qr_code(test_data)
        assert result.is_success()
        
        # Check display is active
        assert display_adapter.is_display_active()
        
        # Check displayed content
        content = display_adapter.get_displayed_content()
        assert content is not None
        assert content["type"] == "qr_code"
        assert content["data"] == test_data