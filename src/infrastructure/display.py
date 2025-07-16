"""
Display service implementation with consistent error handling using Result pattern
Enhanced with standardized error handling patterns and resource management
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from ..common.error_handling_patterns import (
    ErrorHandlingMixin,
    ResourceManager,
    operation_context,
    with_error_handling,
)
from ..common.result_handling import Result
from ..domain.configuration import DisplayConfig
from ..domain.errors import DisplayError, ErrorCode, ErrorSeverity
from ..interfaces import IDisplayService, ILogger

# Try to import QR code and PIL libraries
try:
    import qrcode
    from PIL import Image, ImageDraw, ImageFont

    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False


class DisplayService(IDisplayService, ErrorHandlingMixin):
    """Concrete implementation of display service optimized for ROCK Pi 4B+ with enhanced error handling"""

    def __init__(self, config: DisplayConfig, logger: Optional[ILogger] = None):
        super().__init__()  # Initialize ErrorHandlingMixin
        self.config = config
        self.logger = logger
        self.is_active = False
        self.current_process: Optional[subprocess.Popen] = None

        # ROCK Pi 4B+ specific display configuration
        self.supported_resolutions = self._detect_display_capabilities()
        self.optimal_resolution = self._select_optimal_resolution()
        self.is_4k_capable = self._check_4k_capability()

        # Resource management
        self._resource_manager = ResourceManager(logger)
        self._temp_files: list = []

        if not QR_AVAILABLE:
            if self.logger:
                self.logger.warning(
                    "QR code libraries not available, display functionality will be limited"
                )

        # Configure optimal display settings on initialization
        if self.is_4k_capable:
            self._configure_optimal_display()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with proper cleanup"""
        self._cleanup_resources()

    @with_error_handling("show_qr_code")
    def show_qr_code(self, data: str) -> Result[bool, Exception]:
        """Display QR code with enhanced error handling and resource management"""
        with operation_context("show_qr_code", self.logger, data_length=len(data)):
            try:
                self._add_operation_context("show_qr_code", data_length=len(data))

                if self.logger:
                    self.logger.info("Generating and displaying QR code")

                if not QR_AVAILABLE:
                    if self.logger:
                        self.logger.warning(
                            "QR code display simulated (libraries not available)"
                        )
                    self.is_active = True
                    return self._create_success_result(
                        True, "show_qr_code", simulated=True
                    )

                # Generate QR code with resource tracking
                with self._resource_manager:
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

                    # Create full display image
                    display_img = self._create_display_image(qr_img, data)

                    # Save image with cleanup tracking
                    image_path = "/tmp/provisioning_qr.png"
                    self._temp_files.append(image_path)
                    display_img.save(image_path)

                    # Display image
                    if self._display_image(image_path):
                        self.is_active = True
                        return self._create_success_result(
                            True,
                            "show_qr_code",
                            image_path=image_path,
                            qr_data_length=len(data),
                        )
                    else:
                        return self._create_error_result(
                            DisplayError(
                                ErrorCode.DISPLAY_FAILED,
                                "Failed to display QR code image",
                                ErrorSeverity.MEDIUM,
                            ),
                            "show_qr_code",
                            image_path=image_path,
                        )

            except Exception as e:
                return self._create_error_result(
                    e, "show_qr_code", data_length=len(data)
                )

    def show_status(self, message: str) -> Result[bool, Exception]:
        """Display status message with consistent error handling"""
        try:
            if self.logger:
                self.logger.info(f"Displaying status: {message}")

            if not QR_AVAILABLE:
                if self.logger:
                    self.logger.info(f"Status display simulated: {message}")
                return Result.success(True)

            # Create status image
            status_img = self._create_status_image(message)

            # Save image
            image_path = "/tmp/provisioning_status.png"
            status_img.save(image_path)

            # Display image
            result = self._display_image(image_path)
            return Result.success(result)

        except Exception as e:
            error_msg = f"Failed to show status: {e}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                DisplayError(
                    ErrorCode.DISPLAY_ERROR,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

    def clear_display(self) -> Result[bool, Exception]:
        """Clear the display with consistent error handling"""
        try:
            if self.logger:
                self.logger.info("Clearing display")

            # Stop any running display process
            if self.current_process:
                self.current_process.terminate()
                self.current_process = None

            # Create black screen
            if QR_AVAILABLE:
                black_img = Image.new(
                    "RGB", (self.config.width, self.config.height), "black"
                )
                image_path = "/tmp/provisioning_clear.png"
                black_img.save(image_path)
                self._display_image(image_path)

            self.is_active = False

            if self.logger:
                self.logger.info("Display cleared")

            return Result.success(True)

        except Exception as e:
            error_msg = f"Failed to clear display: {e}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                DisplayError(
                    ErrorCode.DISPLAY_ERROR,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

    def is_display_active(self) -> bool:
        """Check if display is active"""
        return self.is_active

    def _create_display_image(self, qr_img: "Image.Image", data: str) -> "Image.Image":
        """Create full display image with QR code optimized for ROCK Pi 4B+"""
        # Get optimal display size
        width, height, _ = self.optimal_resolution

        # Create base image with optimal resolution
        img = Image.new("RGB", (width, height), self.config.background_color)
        draw = ImageDraw.Draw(img)

        # Calculate optimal QR code size based on resolution
        if self.is_4k_capable and width >= 3840:
            qr_size = getattr(self.config, "qr_code_size_4k", 800)
            title_font_size = 48
            text_font_size = 32
        else:
            qr_size = getattr(self.config, "qr_code_size_1080p", 400)
            title_font_size = 32
            text_font_size = 24

        # Use fallback if config doesn't have the new attributes
        if not hasattr(self.config, "qr_code_size_4k"):
            qr_size = self.config.qr_size

        # Resize QR code for optimal viewing
        qr_resized = qr_img.resize((qr_size, qr_size), Image.Resampling.NEAREST)

        # Calculate positions for centering
        qr_x = (width - qr_size) // 2
        qr_y = (height - qr_size) // 2 - 50  # Offset up for text below

        # Paste QR code
        img.paste(qr_resized, (qr_x, qr_y))

        # Add title and instructions with resolution-appropriate fonts
        try:
            # Try to load appropriate fonts for different resolutions
            try:
                title_font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    title_font_size,
                )
                text_font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", text_font_size
                )
            except OSError:
                # Fallback to default font
                title_font = ImageFont.load_default()
                text_font = ImageFont.load_default()

            # Title
            title_text = "ROCK Pi 4B+ Setup"
            title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_x = (width - title_width) // 2
            title_y = qr_y - title_font_size - 20

            draw.text(
                (title_x, title_y),
                title_text,
                font=title_font,
                fill=self.config.text_color,
            )

            # Instructions
            instructions = [
                "1. Scan QR code with your mobile device",
                "2. Connect to WiFi network",
                "3. Complete device setup",
                f"Device ID: {data.split(':')[1] if ':' in data else 'Unknown'}",
            ]

            text_y = qr_y + qr_size + 20
            for instruction in instructions:
                text_bbox = draw.textbbox((0, 0), instruction, font=text_font)
                text_width = text_bbox[2] - text_bbox[0]
                text_x = (width - text_width) // 2

                draw.text(
                    (text_x, text_y),
                    instruction,
                    font=text_font,
                    fill=self.config.text_color,
                )
                text_y += text_font_size + 10

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Font rendering failed, using basic text: {e}")

        return img

        # Resize QR code
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

        # Center QR code
        qr_x = (width - qr_size) // 2
        qr_y = (height - qr_size) // 2 - 50

        img.paste(qr_img, (qr_x, qr_y))

        # Add title text with optimal font size
        try:
            title_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", title_font_size
            )
        except:
            title_font = ImageFont.load_default()

        # Enhanced title for ROCK Pi 4B+
        title = "ROCK Pi 4B+ Setup"
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (width - title_width) // 2
        title_y = qr_y - 80

        draw.text(
            (title_x, title_y), title, fill=self.config.text_color, font=title_font
        )

        # Add instruction text
        try:
            font_small = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", text_font_size
            )
        except:
            font_small = ImageFont.load_default()

        instruction = "Scan QR code with mobile app to configure WiFi"
        inst_bbox = draw.textbbox((0, 0), instruction, font=font_small)
        inst_width = inst_bbox[2] - inst_bbox[0]
        inst_x = (width - inst_width) // 2
        inst_y = qr_y + qr_size + 30

        draw.text(
            (inst_x, inst_y), instruction, fill=self.config.text_color, font=font_small
        )

        return img

    def _create_status_image(self, message: str) -> "Image.Image":
        """Create status display image"""
        img = Image.new(
            "RGB", (self.config.width, self.config.height), self.config.background_color
        )
        draw = ImageDraw.Draw(img)

        # Add status text
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                self.config.status_font_size,
            )
        except:
            font = ImageFont.load_default()

        # Center text
        text_bbox = draw.textbbox((0, 0), message, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        text_x = (self.config.width - text_width) // 2
        text_y = (self.config.height - text_height) // 2

        draw.text((text_x, text_y), message, fill=self.config.text_color, font=font)

        return img

    def _display_image(self, image_path: str) -> bool:
        """Display image on screen"""
        try:
            # Check if we have a display
            if not os.environ.get("DISPLAY") and not os.path.exists("/dev/fb0"):
                if self.logger:
                    self.logger.warning("No display available")
                self.is_active = True  # Simulate success
                return True

            # Try different image viewers
            viewers = ["feh", "eog", "display", "fim"]

            for viewer in viewers:
                try:
                    if viewer == "feh":
                        # feh with fullscreen
                        self.current_process = subprocess.Popen(
                            ["feh", "--fullscreen", "--hide-pointer", image_path]
                        )
                    elif viewer == "eog":
                        # Eye of GNOME
                        self.current_process = subprocess.Popen(
                            ["eog", "--fullscreen", image_path]
                        )
                    elif viewer == "display":
                        # ImageMagick display
                        self.current_process = subprocess.Popen(
                            ["display", "-window", "root", image_path]
                        )
                    elif viewer == "fim":
                        # Frame buffer image viewer
                        self.current_process = subprocess.Popen(
                            ["fim", "-a", image_path]
                        )

                    self.is_active = True
                    if self.logger:
                        self.logger.info(f"Image displayed using {viewer}")
                    return True

                except FileNotFoundError:
                    continue
                except Exception as e:
                    if self.logger:
                        self.logger.debug(f"{viewer} failed: {e}")
                    continue

            # Fallback: copy to a known location
            import shutil

            shutil.copy2(image_path, "/tmp/current_display.png")
            self.is_active = True

            if self.logger:
                self.logger.warning(
                    "No image viewer found, image saved to /tmp/current_display.png"
                )

            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to display image: {e}")
            return False

    def _detect_display_capabilities(self) -> list[tuple[int, int, int]]:
        """Detect connected display capabilities via EDID"""
        try:
            # Use xrandr to get supported resolutions
            result = subprocess.run(
                ["xrandr", "--query"], capture_output=True, text=True, timeout=10
            )

            resolutions = []
            current_output = None

            for line in result.stdout.split("\n"):
                if " connected" in line:
                    current_output = line.split()[0]
                elif current_output and "x" in line and "Hz" in line:
                    parts = line.strip().split()
                    if parts:
                        resolution_part = parts[0]
                        if "x" in resolution_part:
                            try:
                                width, height = map(int, resolution_part.split("x"))
                                # Extract refresh rate
                                refresh_rates = [
                                    float(p.rstrip("*+"))
                                    for p in parts[1:]
                                    if p.replace(".", "")
                                    .replace("*", "")
                                    .replace("+", "")
                                    .isdigit()
                                ]
                                for rate in refresh_rates:
                                    resolutions.append((width, height, int(rate)))
                            except ValueError:
                                continue

            return resolutions or [(1920, 1080, 60)]  # Fallback

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Display capability detection failed: {e}")
            return [(1920, 1080, 60)]

    def _select_optimal_resolution(self) -> tuple[int, int, int]:
        """Select optimal resolution for QR code display"""
        # Prefer 4K if available, otherwise 1080p
        for width, height, refresh in self.supported_resolutions:
            if width >= 3840 and height >= 2160 and refresh >= 30:
                return (3840, 2160, min(60, refresh))

        for width, height, refresh in self.supported_resolutions:
            if width >= 1920 and height >= 1080:
                return (width, height, min(60, refresh))

        return (1920, 1080, 60)  # Safe fallback

    def _check_4k_capability(self) -> bool:
        """Check if 4K display is supported and available"""
        try:
            for width, height, _ in self.supported_resolutions:
                if width >= 3840 and height >= 2160:
                    return True
            return False
        except Exception:
            return False

    def _configure_optimal_display(self) -> bool:
        """Configure display for optimal QR code viewing"""
        try:
            width, height, refresh = self.optimal_resolution

            # Set optimal resolution
            cmd = [
                "xrandr",
                "--output",
                "HDMI-1",
                "--mode",
                f"{width}x{height}",
                "--rate",
                str(refresh),
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=10)

            if result.returncode == 0:
                if self.logger:
                    self.logger.info(
                        f"Display configured to {width}x{height}@{refresh}Hz"
                    )
                return True
            else:
                if self.logger:
                    self.logger.warning(
                        f"Display configuration failed: {result.stderr}"
                    )
                return False

        except Exception as e:
            if self.logger:
                self.logger.error(f"Display configuration error: {e}")
            return False

    def _cleanup_resources(self) -> None:
        """Clean up display resources and temporary files"""
        try:
            # Stop any active display processes
            if self.current_process:
                try:
                    self.current_process.terminate()
                    self.current_process.wait(timeout=5)
                except (subprocess.TimeoutExpired, OSError):
                    if self.current_process.poll() is None:
                        self.current_process.kill()
                finally:
                    self.current_process = None

            # Clean up temporary files
            for temp_file in self._temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        if self.logger:
                            self.logger.debug(f"Removed temporary file: {temp_file}")
                except OSError as e:
                    if self.logger:
                        self.logger.warning(
                            f"Failed to remove temporary file {temp_file}: {e}"
                        )

            self._temp_files.clear()
            self.is_active = False

            if self.logger:
                self.logger.info("Display resources cleaned up successfully")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error during display resource cleanup: {e}")

    @with_error_handling("stop_display")
    def stop_display(self) -> Result[bool, Exception]:
        """Stop display with enhanced error handling and cleanup"""
        with operation_context("stop_display", self.logger):
            try:
                self._add_operation_context("stop_display", was_active=self.is_active)

                if not self.is_active:
                    return self._create_success_result(
                        True, "stop_display", already_stopped=True
                    )

                self._cleanup_resources()

                return self._create_success_result(
                    True, "stop_display", cleanup_completed=True
                )

            except Exception as e:
                return self._create_error_result(e, "stop_display")
