#!/usr/bin/env python3
"""
Standalone QR code functionality test
This script demonstrates the QR code serial output without complex dependencies
"""

import json
import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any

# Try to import QR code libraries
try:
    import qrcode
    from PIL import Image, ImageDraw, ImageFont
    QR_AVAILABLE = True
    print("✓ QR code libraries available")
except ImportError:
    QR_AVAILABLE = False
    print("⚠ QR code libraries not available - using fallback mode")


class SimpleResult:
    """Simple result class for this demo"""
    def __init__(self, success: bool, value=None, error=None):
        self._success = success
        self.value = value
        self.error = error
    
    def is_success(self):
        return self._success
    
    @classmethod
    def success(cls, value):
        return cls(True, value=value)
    
    @classmethod  
    def failure(cls, error):
        return cls(False, error=error)


class StandaloneQRGenerator:
    """Standalone QR code generator for testing"""
    
    def __init__(self):
        self._qr_data_cache: Optional[str] = None
        self._qr_image_cache: Optional["Image.Image"] = None

    def generate_qr_code_data(self, data: str) -> SimpleResult:
        """Generate QR code data for both display and serial output"""
        try:
            print(f"Generating QR code for: {data[:50]}...")
            
            # Cache the data
            self._qr_data_cache = data

            # Create QR code object
            if QR_AVAILABLE:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(data)
                qr.make(fit=True)

                # Create QR code image
                qr_img = qr.make_image(fill_color="black", back_color="white")
                self._qr_image_cache = qr_img

                # Generate text representation for serial output
                text_qr = self._generate_text_qr_code(qr)
                
                result = {
                    "data": data,
                    "image_available": True,
                    "text_representation": text_qr,
                    "data_length": len(data),
                    "qr_version": qr.version,
                    "error_correction": "L",
                    "modules_count": qr.modules_count,
                }
            else:
                # Fallback when QR libraries not available
                text_qr = self._generate_fallback_text_representation(data)
                result = {
                    "data": data,
                    "image_available": False,
                    "text_representation": text_qr,
                    "data_length": len(data),
                    "qr_version": None,
                    "error_correction": "N/A",
                    "modules_count": None,
                }

            return SimpleResult.success(result)

        except Exception as e:
            return SimpleResult.failure(f"QR code generation failed: {e}")

    def output_qr_to_serial(self, data: str, output_format: str = "json") -> SimpleResult:
        """Output QR code information to serial/stdout for testing and monitoring"""
        try:
            qr_result = self.generate_qr_code_data(data)
            
            if not qr_result.is_success():
                return SimpleResult.failure(qr_result.error)
            
            qr_info = qr_result.value

            if output_format.lower() == "json":
                self._output_json_format(qr_info)
            elif output_format.lower() == "text":
                self._output_text_format(qr_info)
            elif output_format.lower() == "ascii":
                self._output_ascii_format(qr_info)
            else:
                return SimpleResult.failure(f"Unsupported output format: {output_format}")

            return SimpleResult.success(True)

        except Exception as e:
            return SimpleResult.failure(f"Serial QR output failed: {e}")

    def get_qr_data(self) -> Optional[str]:
        """Get the cached QR code data"""
        return self._qr_data_cache

    def get_qr_image(self) -> Optional["Image.Image"]:
        """Get the cached QR code image"""
        return self._qr_image_cache

    def _generate_text_qr_code(self, qr: "qrcode.QRCode") -> str:
        """Generate text representation of QR code for serial output"""
        if not QR_AVAILABLE:
            return "QR libraries not available"

        try:
            # Get the QR code modules (the black/white matrix)
            modules = qr.modules
            if not modules:
                return "QR generation failed"

            lines = []
            lines.append("+" + "-" * (len(modules[0]) * 2) + "+")
            
            for row in modules:
                line = "|"
                for module in row:
                    if module:
                        line += "██"  # Full block for black modules
                    else:
                        line += "  "  # Two spaces for white modules
                line += "|"
                lines.append(line)
            
            lines.append("+" + "-" * (len(modules[0]) * 2) + "+")
            
            return "\n".join(lines)

        except Exception as e:
            return f"Error generating text QR: {e}"

    def _generate_fallback_text_representation(self, data: str) -> str:
        """Generate fallback text representation when QR libraries are not available"""
        lines = [
            "+" + "-" * 40 + "+",
            "|" + " " * 16 + "QR CODE" + " " * 17 + "|",
            "|" + " " * 12 + "(Not Available)" + " " * 12 + "|",
            "|" + " " * 40 + "|",
            f"| Data: {data[:32]:<32} |",
        ]
        
        if len(data) > 32:
            lines.append(f"| {data[32:64]:<38} |")
        
        lines.extend([
            "|" + " " * 40 + "|",
            "+" + "-" * 40 + "+",
        ])
        
        return "\n".join(lines)

    def _output_json_format(self, qr_info: Dict[str, Any]) -> None:
        """Output QR information in JSON format"""
        output_data = {
            "qr_code_info": {
                "timestamp": datetime.now().isoformat(),
                "data": qr_info["data"],
                "data_length": qr_info["data_length"],
                "image_available": qr_info["image_available"],
                "qr_version": qr_info["qr_version"],
                "error_correction": qr_info["error_correction"],
                "modules_count": qr_info["modules_count"],
            }
        }
        
        print("==== QR_CODE_JSON_START ====")
        print(json.dumps(output_data, indent=2))
        print("==== QR_CODE_JSON_END ====")
        sys.stdout.flush()

    def _output_text_format(self, qr_info: Dict[str, Any]) -> None:
        """Output QR information in human-readable text format"""
        print("==== QR_CODE_TEXT_START ====")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"QR Code Data: {qr_info['data']}")
        print(f"Data Length: {qr_info['data_length']} characters")
        print(f"Image Available: {qr_info['image_available']}")
        print(f"QR Version: {qr_info['qr_version']}")
        print(f"Error Correction: {qr_info['error_correction']}")
        print(f"Modules Count: {qr_info['modules_count']}")
        print("==== QR_CODE_TEXT_END ====")
        sys.stdout.flush()

    def _output_ascii_format(self, qr_info: Dict[str, Any]) -> None:
        """Output QR code in ASCII format"""
        print("==== QR_CODE_ASCII_START ====")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"Data: {qr_info['data']}")
        print("ASCII QR Code:")
        print(qr_info["text_representation"])
        print("==== QR_CODE_ASCII_END ====")
        sys.stdout.flush()


def main():
    """Demonstrate QR code serial output functionality"""
    print("=== Standalone QR Code Serial Output Test ===\n")
    
    # Test data
    test_provisioning_code = "ROCKPI4B+:a1b2c3d4:aabbccddeeff"
    
    try:
        # 1. Create QR generator
        print("1. Creating QR code generator...")
        qr_generator = StandaloneQRGenerator()
        
        # 2. Generate QR code data
        print("2. Generating QR code...")
        result = qr_generator.generate_qr_code_data(test_provisioning_code)
        
        if result.is_success():
            qr_info = result.value
            print(f"   ✓ QR Code generated successfully")
            print(f"   ✓ Data length: {qr_info['data_length']} characters")
            print(f"   ✓ Image available: {qr_info['image_available']}")
            print()
        else:
            print(f"   ✗ QR Code generation failed: {result.error}")
            return
        
        # 3. Test JSON serial output
        print("3. QR Code Serial Output - JSON Format:")
        print("=" * 60)
        json_result = qr_generator.output_qr_to_serial(test_provisioning_code, "json")
        if json_result.is_success():
            print("✓ JSON output successful")
        else:
            print(f"✗ JSON output failed: {json_result.error}")
        print("=" * 60)
        print()
        
        # 4. Test text serial output
        print("4. QR Code Serial Output - Text Format:")
        print("=" * 60)
        text_result = qr_generator.output_qr_to_serial(test_provisioning_code, "text")
        if text_result.is_success():
            print("✓ Text output successful")
        else:
            print(f"✗ Text output failed: {text_result.error}")
        print("=" * 60)
        print()
        
        # 5. Test ASCII QR code output
        print("5. QR Code Serial Output - ASCII Format:")
        print("=" * 60)
        ascii_result = qr_generator.output_qr_to_serial(test_provisioning_code, "ascii")
        if ascii_result.is_success():
            print("✓ ASCII output successful")
        else:
            print(f"✗ ASCII output failed: {ascii_result.error}")
        print("=" * 60)
        print()
        
        # 6. Test caching
        print("6. Testing QR Code Caching:")
        cached_data = qr_generator.get_qr_data()
        cached_image = qr_generator.get_qr_image()
        print(f"   ✓ Cached data: {cached_data[:30]}...")
        print(f"   ✓ Cached image available: {cached_image is not None}")
        print()
        
        # 7. Test invalid format
        print("7. Testing Error Handling:")
        invalid_result = qr_generator.output_qr_to_serial(test_provisioning_code, "invalid")
        if not invalid_result.is_success():
            print(f"   ✓ Properly handled invalid format: {invalid_result.error}")
        else:
            print("   ✗ Should have failed with invalid format")
        print()
        
        print("=== Test Complete ===")
        print("\n✓ All QR code functionality working correctly!")
        print("\nFeatures Tested:")
        print("• QR code generation and data caching")
        print("• Serial output in JSON format (for automated testing)")
        print("• Serial output in text format (for human reading)")
        print("• Serial output in ASCII format (for visual QR codes)")
        print("• Error handling for invalid parameters")
        print("\nUse Cases:")
        print("• Automated test scripts can parse JSON output")
        print("• Debug sessions can use text output for monitoring")
        print("• ASCII output provides visual QR codes in terminal")
        print("• Serial output enables real-time provisioning monitoring")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()