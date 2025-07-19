"""
QR Code generation and output module with display and serial capabilities
"""

import json
import os
import sys
from typing import Optional, Dict, Any

from ...common.result_handling import Result
from ...domain.errors import DisplayError, ErrorCode, ErrorSeverity
from ...interfaces import ILogger

# Try to import QR code and PIL libraries
try:
    import qrcode
    from PIL import Image, ImageDraw, ImageFont
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False


class QRCodeGenerator:
    """QR Code generator with multiple output capabilities"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self._qr_data_cache: Optional[str] = None
        self._qr_image_cache: Optional["Image.Image"] = None

    def generate_qr_code_data(self, data: str) -> Result[dict, Exception]:
        """Generate QR code data for both display and serial output"""
        try:
            if self.logger:
                self.logger.info(f"Generating QR code for data: {data[:50]}...")

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

            return Result.success(result)

        except Exception as e:
            if self.logger:
                self.logger.error(f"QR code generation failed: {e}")
            return Result.failure(
                DisplayError(
                    message=f"QR code generation failed: {e}",
                    error_code=ErrorCode.DISPLAY_ERROR,
                    severity=ErrorSeverity.HIGH,
                )
            )

    def get_qr_image(self) -> Optional["Image.Image"]:
        """Get the cached QR code image"""
        return self._qr_image_cache

    def get_qr_data(self) -> Optional[str]:
        """Get the cached QR code data"""
        return self._qr_data_cache

    def output_qr_to_serial(self, data: str, output_format: str = "json") -> Result[bool, Exception]:
        """Output QR code information to serial/stdout for testing and monitoring"""
        try:
            qr_result = self.generate_qr_code_data(data)
            
            if not qr_result.is_success():
                return Result.failure(qr_result.error)
            
            qr_info = qr_result.value

            if output_format.lower() == "json":
                self._output_json_format(qr_info)
            elif output_format.lower() == "text":
                self._output_text_format(qr_info)
            elif output_format.lower() == "ascii":
                self._output_ascii_format(qr_info)
            else:
                return Result.failure(
                    DisplayError(
                        message=f"Unsupported output format: {output_format}",
                        error_code=ErrorCode.DISPLAY_ERROR,
                        severity=ErrorSeverity.MEDIUM,
                    )
                )

            return Result.success(True)

        except Exception as e:
            if self.logger:
                self.logger.error(f"Serial QR output failed: {e}")
            return Result.failure(
                DisplayError(
                    message=f"Serial QR output failed: {e}",
                    error_code=ErrorCode.DISPLAY_ERROR,
                    severity=ErrorSeverity.MEDIUM,
                )
            )

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
            if self.logger:
                self.logger.error(f"Text QR generation failed: {e}")
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
                "timestamp": self._get_timestamp(),
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
        print(f"Timestamp: {self._get_timestamp()}")
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
        print(f"Timestamp: {self._get_timestamp()}")
        print(f"Data: {qr_info['data']}")
        print("ASCII QR Code:")
        print(qr_info["text_representation"])
        print("==== QR_CODE_ASCII_END ====")
        sys.stdout.flush()

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.now().isoformat()

    def create_display_image(self, qr_img: "Image.Image", data: str, 
                           width: int = 1920, height: int = 1080,
                           background_color: str = "white") -> "Image.Image":
        """Create full display image with QR code optimized for different resolutions"""
        if not QR_AVAILABLE:
            raise RuntimeError("PIL not available for image creation")

        # Create base image
        img = Image.new("RGB", (width, height), background_color)
        draw = ImageDraw.Draw(img)

        # Calculate optimal QR code size based on resolution
        if width >= 3840:  # 4K
            qr_size = 800
            title_font_size = 48
            text_font_size = 32
        elif width >= 1920:  # 1080p
            qr_size = 400
            title_font_size = 32
            text_font_size = 24
        else:  # Lower resolution
            qr_size = 300
            title_font_size = 24
            text_font_size = 18

        # Resize QR code
        qr_resized = qr_img.resize((qr_size, qr_size), Image.Resampling.NEAREST)

        # Position QR code in center
        qr_x = (width - qr_size) // 2
        qr_y = (height - qr_size) // 2

        # Paste QR code onto base image
        img.paste(qr_resized, (qr_x, qr_y))

        # Add title text
        try:
            # Try to use a reasonable font
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", title_font_size)
            text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", text_font_size)
        except (OSError, IOError):
            # Fallback to default font
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()

        # Add title
        title = "Device Provisioning"
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (width - title_width) // 2
        title_y = qr_y - title_font_size - 20
        draw.text((title_x, title_y), title, fill="black", font=title_font)

        # Add instruction text
        instruction = "Scan QR code to provision device"
        instruction_bbox = draw.textbbox((0, 0), instruction, font=text_font)
        instruction_width = instruction_bbox[2] - instruction_bbox[0]
        instruction_x = (width - instruction_width) // 2
        instruction_y = qr_y + qr_size + 20
        draw.text((instruction_x, instruction_y), instruction, fill="black", font=text_font)

        return img