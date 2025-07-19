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
from .display.qr_generator import QRCodeGenerator

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

        # Enhanced resource management with context managers
        self._resource_manager = ResourceManager(logger)
        self._temp_files: list = []
        self._cleanup_callbacks: list = []
        self._active_contexts: list = []
        
        # QR code generator
        self.qr_generator = QRCodeGenerator(logger)

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
    def show_qr_code(self, data: str, enable_serial_output: bool = True, 
                     serial_format: str = "json") -> Result[bool, Exception]:
        """Display QR code with enhanced error handling and resource management"""
        with operation_context("show_qr_code", self.logger, data_length=len(data)):
            try:
                self._add_operation_context("show_qr_code", data_length=len(data))

                if self.logger:
                    self.logger.info("Generating and displaying QR code")

                # Generate QR code data using the new generator
                qr_result = self.qr_generator.generate_qr_code_data(data)
                if not qr_result.is_success():
                    return Result.failure(qr_result.error)
                
                # Output QR code information to serial if enabled
                if enable_serial_output:
                    serial_result = self.qr_generator.output_qr_to_serial(data, serial_format)
                    if not serial_result.is_success() and self.logger:
                        self.logger.warning(f"Serial output failed: {serial_result.error}")

                if not QR_AVAILABLE:
                    if self.logger:
                        self.logger.warning(
                            "QR code display simulated (libraries not available)"
                        )
                    self.is_active = True
                    return self._create_success_result(
                        True, "show_qr_code", simulated=True
                    )

                # Get the generated QR image
                qr_img = self.qr_generator.get_qr_image()
                if not qr_img:
                    return self._create_error_result(
                        DisplayError(
                            message="Failed to generate QR code image",
                            error_code=ErrorCode.DISPLAY_ERROR,
                            severity=ErrorSeverity.HIGH,
                        ),
                        "show_qr_code"
                    )

                # Generate QR code with resource tracking
                with self._resource_manager:
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
                            serial_output_enabled=enable_serial_output,
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

        # Use the QR generator to create the display image
        return self.qr_generator.create_display_image(
            qr_img, data, width, height, self.config.background_color
        )



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

            # Clean up temporary files with proper error handling
            cleanup_errors = []
            
            for temp_file in self._temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        if self.logger:
                            self.logger.debug(f"Removed temporary file: {temp_file}")
                except OSError as e:
                    cleanup_errors.append(f"Failed to remove {temp_file}: {e}")
                    if self.logger:
                        self.logger.warning(f"Failed to remove temporary file {temp_file}: {e}")

            # Execute cleanup callbacks
            for callback in self._cleanup_callbacks:
                try:
                    callback()
                except Exception as e:
                    cleanup_errors.append(f"Cleanup callback failed: {e}")
                    if self.logger:
                        self.logger.warning(f"Cleanup callback failed: {e}")

            # Close active contexts
            for context in self._active_contexts:
                try:
                    if hasattr(context, '__exit__'):
                        context.__exit__(None, None, None)
                except Exception as e:
                    cleanup_errors.append(f"Context cleanup failed: {e}")
                    if self.logger:
                        self.logger.warning(f"Context cleanup failed: {e}")

            # Clear all lists
            self._temp_files.clear()
            self._cleanup_callbacks.clear()
            self._active_contexts.clear()
            self.is_active = False

            if cleanup_errors and self.logger:
                self.logger.warning(f"Some cleanup operations failed: {'; '.join(cleanup_errors)}")
            elif self.logger:
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

    def get_current_qr_code_info(self) -> Optional[dict]:
        """Get information about the currently displayed QR code for testing"""
        if not self.qr_generator:
            return None
        
        data = self.qr_generator.get_qr_data()
        if not data:
            return None
        
        # Generate QR info without actually displaying
        qr_result = self.qr_generator.generate_qr_code_data(data)
        if qr_result.is_success():
            return qr_result.value
        return None

    def output_qr_to_serial(self, format: str = "json") -> Result[bool, Exception]:
        """Output current QR code information to serial for testing"""
        try:
            data = self.qr_generator.get_qr_data() if self.qr_generator else None
            if not data:
                return Result.failure(
                    DisplayError(
                        message="No QR code data available",
                        error_code=ErrorCode.DISPLAY_ERROR,
                        severity=ErrorSeverity.MEDIUM,
                    )
                )
            
            return self.qr_generator.output_qr_to_serial(data, format)
            
        except Exception as e:
            return Result.failure(
                DisplayError(
                    message=f"Serial output failed: {e}",
                    error_code=ErrorCode.DISPLAY_ERROR,
                    severity=ErrorSeverity.MEDIUM,
                )
            )
    
    def register_temp_file(self, filepath: str):
        """Register a temporary file for cleanup"""
        if filepath not in self._temp_files:
            self._temp_files.append(filepath)
    
    def register_cleanup_callback(self, callback):
        """Register a cleanup callback to be executed during shutdown"""
        self._cleanup_callbacks.append(callback)
    
    def register_context(self, context):
        """Register a context manager for cleanup"""
        self._active_contexts.append(context)
        
    def create_temp_file_context(self, filepath: str):
        """Create a context manager for temporary file handling"""
        return TempFileContext(filepath, self)


class TempFileContext:
    """Context manager for temporary file cleanup"""
    
    def __init__(self, filepath: str, display_service):
        self.filepath = filepath
        self.display_service = display_service
    
    def __enter__(self):
        self.display_service.register_temp_file(self.filepath)
        return self.filepath
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if os.path.exists(self.filepath):
                os.remove(self.filepath)
                if self.display_service.logger:
                    self.display_service.logger.debug(f"Cleaned up temporary file: {self.filepath}")
        except OSError as e:
            if self.display_service.logger:
                self.display_service.logger.warning(f"Failed to clean up temporary file {self.filepath}: {e}")
        finally:
            # Remove from tracking list
            if self.filepath in self.display_service._temp_files:
                self.display_service._temp_files.remove(self.filepath)
