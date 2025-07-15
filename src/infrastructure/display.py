"""
Display service implementation
"""

import os
import subprocess
from typing import Optional
from pathlib import Path
from ..interfaces import IDisplayService, ILogger
from ..domain.configuration import DisplayConfig
from ..domain.errors import DisplayError, ErrorCode, ErrorSeverity

# Try to import QR code and PIL libraries
try:
    import qrcode
    from PIL import Image, ImageDraw, ImageFont
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False


class DisplayService(IDisplayService):
    """Concrete implementation of display service"""
    
    def __init__(self, config: DisplayConfig, logger: Optional[ILogger] = None):
        self.config = config
        self.logger = logger
        self.is_active = False
        self.current_process: Optional[subprocess.Popen] = None
        
        if not QR_AVAILABLE:
            if self.logger:
                self.logger.warning("QR code libraries not available, display functionality will be limited")
    
    def show_qr_code(self, data: str) -> bool:
        """Display QR code"""
        try:
            if self.logger:
                self.logger.info("Generating and displaying QR code")
            
            if not QR_AVAILABLE:
                if self.logger:
                    self.logger.warning("QR code display simulated (libraries not available)")
                self.is_active = True
                return True
            
            # Generate QR code
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
            
            # Save image
            image_path = "/tmp/provisioning_qr.png"
            display_img.save(image_path)
            
            # Display image
            return self._display_image(image_path)
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to show QR code: {e}")
            raise DisplayError(
                ErrorCode.QR_CODE_GENERATION_FAILED,
                f"Failed to generate/display QR code: {str(e)}",
                ErrorSeverity.MEDIUM
            )
    
    def show_status(self, message: str) -> bool:
        """Display status message"""
        try:
            if self.logger:
                self.logger.info(f"Displaying status: {message}")
            
            if not QR_AVAILABLE:
                if self.logger:
                    self.logger.info(f"Status display simulated: {message}")
                return True
            
            # Create status image
            status_img = self._create_status_image(message)
            
            # Save image
            image_path = "/tmp/provisioning_status.png"
            status_img.save(image_path)
            
            # Display image
            return self._display_image(image_path)
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to show status: {e}")
            return False
    
    def clear_display(self) -> bool:
        """Clear the display"""
        try:
            if self.logger:
                self.logger.info("Clearing display")
            
            # Stop any running display process
            if self.current_process:
                self.current_process.terminate()
                self.current_process = None
            
            # Create black screen
            if QR_AVAILABLE:
                black_img = Image.new('RGB', (self.config.width, self.config.height), 'black')
                image_path = "/tmp/provisioning_clear.png"
                black_img.save(image_path)
                self._display_image(image_path)
            
            self.is_active = False
            
            if self.logger:
                self.logger.info("Display cleared")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to clear display: {e}")
            return False
    
    def is_display_active(self) -> bool:
        """Check if display is active"""
        return self.is_active
    
    def _create_display_image(self, qr_img: 'Image.Image', data: str) -> 'Image.Image':
        """Create full display image with QR code and text"""
        # Create base image
        img = Image.new('RGB', (self.config.width, self.config.height), self.config.background_color)
        draw = ImageDraw.Draw(img)
        
        # Resize QR code
        qr_size = self.config.qr_size
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
        
        # Center QR code
        qr_x = (self.config.width - qr_size) // 2
        qr_y = (self.config.height - qr_size) // 2 - 50
        
        img.paste(qr_img, (qr_x, qr_y))
        
        # Add title text
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        except:
            font = ImageFont.load_default()
        
        title = "Rock Pi 3399 Setup"
        title_bbox = draw.textbbox((0, 0), title, font=font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (self.config.width - title_width) // 2
        title_y = qr_y - 80
        
        draw.text((title_x, title_y), title, fill=self.config.text_color, font=font)
        
        # Add instruction text
        try:
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except:
            font_small = ImageFont.load_default()
        
        instruction = "Scan QR code with mobile app to configure WiFi"
        inst_bbox = draw.textbbox((0, 0), instruction, font=font_small)
        inst_width = inst_bbox[2] - inst_bbox[0]
        inst_x = (self.config.width - inst_width) // 2
        inst_y = qr_y + qr_size + 30
        
        draw.text((inst_x, inst_y), instruction, fill=self.config.text_color, font=font_small)
        
        return img
    
    def _create_status_image(self, message: str) -> 'Image.Image':
        """Create status display image"""
        img = Image.new('RGB', (self.config.width, self.config.height), self.config.background_color)
        draw = ImageDraw.Draw(img)
        
        # Add status text
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", self.config.status_font_size)
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
            if not os.environ.get('DISPLAY') and not os.path.exists('/dev/fb0'):
                if self.logger:
                    self.logger.warning("No display available")
                self.is_active = True  # Simulate success
                return True
            
            # Try different image viewers
            viewers = ['feh', 'eog', 'display', 'fim']
            
            for viewer in viewers:
                try:
                    if viewer == 'feh':
                        # feh with fullscreen
                        self.current_process = subprocess.Popen([
                            'feh', '--fullscreen', '--hide-pointer', image_path
                        ])
                    elif viewer == 'eog':
                        # Eye of GNOME
                        self.current_process = subprocess.Popen([
                            'eog', '--fullscreen', image_path
                        ])
                    elif viewer == 'display':
                        # ImageMagick display
                        self.current_process = subprocess.Popen([
                            'display', '-window', 'root', image_path
                        ])
                    elif viewer == 'fim':
                        # Frame buffer image viewer
                        self.current_process = subprocess.Popen([
                            'fim', '-a', image_path
                        ])
                    
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
                self.logger.warning("No image viewer found, image saved to /tmp/current_display.png")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to display image: {e}")
            return False


class MockDisplayService(IDisplayService):
    """Mock implementation for testing"""
    
    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.is_active = False
    
    def show_qr_code(self, data: str) -> bool:
        if self.logger:
            self.logger.info(f"Mock QR code displayed: {data}")
        self.is_active = True
        return True
    
    def show_status(self, message: str) -> bool:
        if self.logger:
            self.logger.info(f"Mock status displayed: {message}")
        return True
    
    def clear_display(self) -> bool:
        if self.logger:
            self.logger.info("Mock display cleared")
        self.is_active = False
        return True
    
    def is_display_active(self) -> bool:
        return self.is_active
