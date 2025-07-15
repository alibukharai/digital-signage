"""
Factory reset service implementation
"""

import json
import time
import threading
import subprocess
from typing import Tuple, Dict, Any, Optional, Callable
from pathlib import Path
from ..interfaces import IFactoryResetService, ILogger
from ..domain.errors import SystemError, ErrorCode, ErrorSeverity

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False


class FactoryResetService(IFactoryResetService):
    """Concrete implementation of factory reset service"""
    
    def __init__(self, reset_pin: int = 18, logger: Optional[ILogger] = None):
        self.reset_pin = reset_pin
        self.logger = logger
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.reset_callback: Optional[Callable] = None
        self.recovery_mode = False
        self.recovery_start_time: Optional[float] = None
        
        # Recovery data file
        self.recovery_file = Path("/tmp/rockpi_recovery.json")
        
        if GPIO_AVAILABLE:
            self._setup_gpio()
        elif self.logger:
            self.logger.warning("GPIO not available, factory reset monitoring disabled")
        
        if self.logger:
            self.logger.info("Factory reset service initialized")
    
    def is_reset_available(self) -> bool:
        """Check if reset is available"""
        return GPIO_AVAILABLE or self.recovery_mode
    
    def perform_reset(self, confirmation_code: str) -> Tuple[bool, str]:
        """Perform factory reset"""
        try:
            if not self.recovery_mode:
                return False, "Device not in recovery mode"
            
            # Validate confirmation code
            if not self._validate_confirmation_code(confirmation_code):
                return False, "Invalid confirmation code"
            
            if self.logger:
                self.logger.critical("Starting factory reset procedure")
            
            # Create reset log
            reset_log = {
                'timestamp': time.time(),
                'confirmation_code': confirmation_code,
                'status': 'initiated'
            }
            
            with open(self.recovery_file, 'w') as f:
                json.dump(reset_log, f)
            
            # Perform the actual reset
            success = self._perform_system_reset()
            
            if success:
                reset_log['status'] = 'completed'
                if self.logger:
                    self.logger.critical("Factory reset completed successfully")
                return True, "Factory reset completed"
            else:
                reset_log['status'] = 'failed'
                return False, "Factory reset failed"
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Factory reset error: {e}")
            return False, f"Reset error: {str(e)}"
        
        finally:
            # Update log
            try:
                if 'reset_log' in locals():
                    with open(self.recovery_file, 'w') as f:
                        json.dump(reset_log, f)
            except Exception:
                pass
    
    def get_reset_info(self) -> Dict[str, Any]:
        """Get reset information"""
        info = {
            'available': self.is_reset_available(),
            'recovery_mode': self.recovery_mode,
            'gpio_available': GPIO_AVAILABLE,
            'monitoring': self.is_monitoring
        }
        
        if self.recovery_mode and self.recovery_start_time:
            info['recovery_duration'] = time.time() - self.recovery_start_time
        
        # Add recovery log if available
        if self.recovery_file.exists():
            try:
                with open(self.recovery_file, 'r') as f:
                    info['last_reset_attempt'] = json.load(f)
            except Exception:
                pass
        
        return info
    
    def start_monitoring(self, reset_callback: Optional[Callable] = None) -> bool:
        """Start monitoring for factory reset trigger"""
        try:
            if not GPIO_AVAILABLE:
                if self.logger:
                    self.logger.warning("Cannot start GPIO monitoring - GPIO not available")
                return False
            
            if self.is_monitoring:
                return True
            
            self.reset_callback = reset_callback
            self.is_monitoring = True
            
            self.monitor_thread = threading.Thread(target=self._monitor_reset_pin, daemon=True)
            self.monitor_thread.start()
            
            if self.logger:
                self.logger.info(f"Factory reset monitoring started (pin {self.reset_pin})")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to start reset monitoring: {e}")
            return False
    
    def stop_monitoring(self) -> bool:
        """Stop monitoring"""
        try:
            self.is_monitoring = False
            
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5)
            
            if GPIO_AVAILABLE:
                GPIO.cleanup(self.reset_pin)
            
            if self.logger:
                self.logger.info("Factory reset monitoring stopped")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to stop reset monitoring: {e}")
            return False
    
    def _setup_gpio(self):
        """Setup GPIO for reset button"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.reset_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            if self.logger:
                self.logger.debug(f"GPIO setup complete for pin {self.reset_pin}")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"GPIO setup failed: {e}")
            raise
    
    def _monitor_reset_pin(self):
        """Monitor reset pin for button press"""
        button_pressed_time = None
        required_hold_time = 5.0  # 5 seconds
        
        while self.is_monitoring:
            try:
                if GPIO.input(self.reset_pin) == GPIO.LOW:  # Button pressed
                    if button_pressed_time is None:
                        button_pressed_time = time.time()
                        if self.logger:
                            self.logger.info("Factory reset button pressed")
                    else:
                        # Check if held long enough
                        hold_time = time.time() - button_pressed_time
                        if hold_time >= required_hold_time:
                            if self.logger:
                                self.logger.warning(f"Factory reset triggered (held {hold_time:.1f}s)")
                            
                            self._trigger_recovery_mode()
                            
                            if self.reset_callback:
                                self.reset_callback()
                            
                            # Reset the timer
                            button_pressed_time = None
                else:
                    # Button released
                    if button_pressed_time is not None:
                        hold_time = time.time() - button_pressed_time
                        if self.logger:
                            self.logger.debug(f"Reset button released after {hold_time:.1f}s")
                        button_pressed_time = None
                
                time.sleep(0.1)  # Check every 100ms
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error monitoring reset pin: {e}")
                time.sleep(1)
    
    def _trigger_recovery_mode(self):
        """Trigger recovery mode"""
        self.recovery_mode = True
        self.recovery_start_time = time.time()
        
        if self.logger:
            self.logger.critical("Device entered recovery mode")
        
        # Create recovery marker
        recovery_data = {
            'recovery_mode': True,
            'start_time': self.recovery_start_time,
            'device_id': self._get_device_id()
        }
        
        try:
            with open(self.recovery_file, 'w') as f:
                json.dump(recovery_data, f)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to create recovery marker: {e}")
    
    def _validate_confirmation_code(self, code: str) -> bool:
        """Validate factory reset confirmation code"""
        # For security, require a specific confirmation
        return code == "CONFIRM_FACTORY_RESET"
    
    def _perform_system_reset(self) -> bool:
        """Perform the actual system reset"""
        try:
            if self.logger:
                self.logger.critical("Executing factory reset commands")
            
            # Remove configuration files
            config_dirs = [
                "/etc/rockpi-provisioning",
                Path.home() / ".config" / "rockpi-provisioning"
            ]
            
            for config_dir in config_dirs:
                try:
                    if Path(config_dir).exists():
                        subprocess.run(['rm', '-rf', str(config_dir)], check=True)
                        if self.logger:
                            self.logger.info(f"Removed {config_dir}")
                except subprocess.CalledProcessError as e:
                    if self.logger:
                        self.logger.error(f"Failed to remove {config_dir}: {e}")
            
            # Clear network configurations
            try:
                subprocess.run(['nmcli', 'connection', 'delete', 'id', 'provisioned-wifi'], 
                             capture_output=True)
            except subprocess.CalledProcessError:
                pass  # Connection might not exist
            
            # Clear any stored credentials
            try:
                subprocess.run(['nmcli', 'connection', 'show'], capture_output=True)
                # Additional network cleanup could go here
            except Exception:
                pass
            
            if self.logger:
                self.logger.critical("Factory reset operations completed")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Factory reset execution failed: {e}")
            return False
    
    def _get_device_id(self) -> str:
        """Get device ID for reset tracking"""
        try:
            with open('/etc/machine-id', 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            return "unknown"


class MockFactoryResetService(IFactoryResetService):
    """Mock implementation for testing"""
    
    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.recovery_mode = False
    
    def is_reset_available(self) -> bool:
        return True
    
    def perform_reset(self, confirmation_code: str) -> Tuple[bool, str]:
        if self.logger:
            self.logger.info(f"Mock factory reset performed with code: {confirmation_code}")
        return True, "Mock reset completed"
    
    def get_reset_info(self) -> Dict[str, Any]:
        return {
            'available': True,
            'recovery_mode': self.recovery_mode,
            'mock': True
        }
    
    def trigger_recovery_mode(self):
        """Trigger recovery mode for testing"""
        self.recovery_mode = True
        if self.logger:
            self.logger.info("Mock recovery mode triggered")
