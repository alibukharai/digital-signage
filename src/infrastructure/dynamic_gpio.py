"""
Dynamic GPIO service implementation that adapts to different SOCs
"""

import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from ..common.result_handling import Result
from ..domain.errors import ErrorCode, ErrorSeverity, SystemError
from ..domain.soc_specifications import SOCFamily, SOCSpecification, soc_manager
from ..interfaces import ILogger

# Try to import GPIO libraries
try:
    import RPi.GPIO as GPIO

    GPIO_AVAILABLE = True
except ImportError:
    try:
        import gpiod

        GPIOD_AVAILABLE = True
        GPIO_AVAILABLE = False
    except ImportError:
        GPIO_AVAILABLE = False
        GPIOD_AVAILABLE = False


class IGPIOBackend(ABC):
    """Abstract GPIO backend interface"""

    @abstractmethod
    def setup_pin(self, pin: int, mode: str, pull: Optional[str] = None) -> bool:
        """Setup a GPIO pin"""
        pass

    @abstractmethod
    def read_pin(self, pin: int) -> bool:
        """Read pin state"""
        pass

    @abstractmethod
    def write_pin(self, pin: int, value: bool) -> bool:
        """Write pin state"""
        pass

    @abstractmethod
    def setup_pwm(self, pin: int, frequency: int) -> Any:
        """Setup PWM on pin"""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup GPIO resources"""
        pass


class RPiGPIOBackend(IGPIOBackend):
    """RPi.GPIO backend implementation"""

    def __init__(self):
        if GPIO_AVAILABLE:
            GPIO.setmode(GPIO.BOARD)
            GPIO.setwarnings(False)

    def setup_pin(self, pin: int, mode: str, pull: Optional[str] = None) -> bool:
        """Setup a GPIO pin using RPi.GPIO"""
        if not GPIO_AVAILABLE:
            return False

        try:
            gpio_mode = GPIO.OUT if mode == "output" else GPIO.IN
            pull_mode = GPIO.PUD_OFF

            if pull == "up":
                pull_mode = GPIO.PUD_UP
            elif pull == "down":
                pull_mode = GPIO.PUD_DOWN

            GPIO.setup(pin, gpio_mode, pull_up_down=pull_mode)
            return True
        except Exception:
            return False

    def read_pin(self, pin: int) -> bool:
        """Read pin state"""
        if not GPIO_AVAILABLE:
            return False
        try:
            return bool(GPIO.input(pin))
        except Exception:
            return False

    def write_pin(self, pin: int, value: bool) -> bool:
        """Write pin state"""
        if not GPIO_AVAILABLE:
            return False
        try:
            GPIO.output(pin, value)
            return True
        except Exception:
            return False

    def setup_pwm(self, pin: int, frequency: int) -> Any:
        """Setup PWM on pin"""
        if not GPIO_AVAILABLE:
            return None
        try:
            pwm = GPIO.PWM(pin, frequency)
            pwm.start(0)
            return pwm
        except Exception:
            return None

    def cleanup(self) -> None:
        """Cleanup GPIO resources"""
        if GPIO_AVAILABLE:
            GPIO.cleanup()


class GpiodBackend(IGPIOBackend):
    """gpiod backend implementation"""

    def __init__(self):
        self.chip = None
        self.lines = {}
        if GPIOD_AVAILABLE:
            try:
                self.chip = gpiod.Chip("gpiochip0")
            except Exception:
                pass

    def setup_pin(self, pin: int, mode: str, pull: Optional[str] = None) -> bool:
        """Setup a GPIO pin using gpiod"""
        if not GPIOD_AVAILABLE or not self.chip:
            return False

        try:
            line = self.chip.get_line(pin)
            if mode == "output":
                line.request(consumer="digital-signage", type=gpiod.LINE_REQ_DIR_OUT)
            else:
                line.request(consumer="digital-signage", type=gpiod.LINE_REQ_DIR_IN)

            self.lines[pin] = line
            return True
        except Exception:
            return False

    def read_pin(self, pin: int) -> bool:
        """Read pin state"""
        if pin not in self.lines:
            return False
        try:
            return bool(self.lines[pin].get_value())
        except Exception:
            return False

    def write_pin(self, pin: int, value: bool) -> bool:
        """Write pin state"""
        if pin not in self.lines:
            return False
        try:
            self.lines[pin].set_value(int(value))
            return True
        except Exception:
            return False

    def setup_pwm(self, pin: int, frequency: int) -> Any:
        """Setup PWM on pin (not directly supported by gpiod)"""
        return None

    def cleanup(self) -> None:
        """Cleanup GPIO resources"""
        for line in self.lines.values():
            try:
                line.release()
            except Exception:
                pass
        self.lines.clear()


class SimulatedGPIOBackend(IGPIOBackend):
    """Simulated GPIO backend for testing/development"""

    def __init__(self):
        self.pin_states = {}
        self.pin_modes = {}

    def setup_pin(self, pin: int, mode: str, pull: Optional[str] = None) -> bool:
        """Setup a simulated GPIO pin"""
        self.pin_modes[pin] = mode
        self.pin_states[pin] = False
        return True

    def read_pin(self, pin: int) -> bool:
        """Read simulated pin state"""
        return self.pin_states.get(pin, False)

    def write_pin(self, pin: int, value: bool) -> bool:
        """Write simulated pin state"""
        self.pin_states[pin] = value
        return True

    def setup_pwm(self, pin: int, frequency: int) -> Any:
        """Setup simulated PWM"""
        return {"pin": pin, "frequency": frequency, "duty_cycle": 0}

    def cleanup(self) -> None:
        """Cleanup simulated GPIO"""
        self.pin_states.clear()
        self.pin_modes.clear()


class DynamicGPIOService:
    """Dynamic GPIO service that adapts to different SOCs"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.soc_spec: Optional[SOCSpecification] = None
        self.gpio_backend: Optional[IGPIOBackend] = None
        self.pin_mapping: Dict[str, int] = {}
        self.button_callbacks: Dict[str, Callable] = {}
        self.pwm_instances: Dict[str, Any] = {}
        self.initialized = False

        self._detect_soc_and_setup()

    def _detect_soc_and_setup(self) -> None:
        """Detect SOC and setup appropriate GPIO backend"""
        # Detect SOC
        self.soc_spec = soc_manager.detect_soc()

        if self.soc_spec:
            self.pin_mapping = self.soc_spec.gpio_mapping.copy()
            if self.logger:
                self.logger.info(f"Detected SOC: {self.soc_spec.name}")
                self.logger.info(f"GPIO pins available: {self.soc_spec.io.gpio_pins}")
        else:
            # Fallback mapping for unknown SOCs
            self.pin_mapping = self._get_generic_pin_mapping()
            if self.logger:
                self.logger.warning("Unknown SOC detected, using generic GPIO mapping")

        # Setup appropriate GPIO backend
        self._setup_gpio_backend()

        # Initialize GPIO
        self._initialize_gpio()

    def _setup_gpio_backend(self) -> None:
        """Setup appropriate GPIO backend based on available libraries and SOC"""
        if self.soc_spec and self.soc_spec.family == SOCFamily.BROADCOM:
            # Raspberry Pi - prefer RPi.GPIO
            if GPIO_AVAILABLE:
                self.gpio_backend = RPiGPIOBackend()
                if self.logger:
                    self.logger.info("Using RPi.GPIO backend for Broadcom SOC")
            elif GPIOD_AVAILABLE:
                self.gpio_backend = GpiodBackend()
                if self.logger:
                    self.logger.info("Using gpiod backend for Broadcom SOC")
            else:
                self.gpio_backend = SimulatedGPIOBackend()
                if self.logger:
                    self.logger.warning("Using simulated GPIO backend")

        elif self.soc_spec and self.soc_spec.family == SOCFamily.ROCKCHIP:
            # Rockchip - prefer gpiod for better support
            if GPIOD_AVAILABLE:
                self.gpio_backend = GpiodBackend()
                if self.logger:
                    self.logger.info("Using gpiod backend for Rockchip SOC")
            elif GPIO_AVAILABLE:
                self.gpio_backend = RPiGPIOBackend()
                if self.logger:
                    self.logger.info("Using RPi.GPIO backend for Rockchip SOC")
            else:
                self.gpio_backend = SimulatedGPIOBackend()
                if self.logger:
                    self.logger.warning("Using simulated GPIO backend")

        elif self.soc_spec and self.soc_spec.family in [
            SOCFamily.ALLWINNER,
            SOCFamily.MEDIATEK,
            SOCFamily.QUALCOMM,
        ]:
            # Other ARM SOCs - prefer gpiod for compatibility
            if GPIOD_AVAILABLE:
                self.gpio_backend = GpiodBackend()
                if self.logger:
                    self.logger.info(
                        f"Using gpiod backend for {self.soc_spec.family.value} SOC"
                    )
            elif GPIO_AVAILABLE:
                self.gpio_backend = RPiGPIOBackend()
                if self.logger:
                    self.logger.info(
                        f"Using RPi.GPIO backend for {self.soc_spec.family.value} SOC"
                    )
            else:
                self.gpio_backend = SimulatedGPIOBackend()
                if self.logger:
                    self.logger.warning(
                        f"Using simulated GPIO backend for {self.soc_spec.family.value} SOC"
                    )

        else:
            # Other SOCs or unknown - try gpiod first, then RPi.GPIO
            if GPIOD_AVAILABLE:
                self.gpio_backend = GpiodBackend()
                if self.logger:
                    self.logger.info("Using gpiod backend for unknown SOC")
            elif GPIO_AVAILABLE:
                self.gpio_backend = RPiGPIOBackend()
                if self.logger:
                    self.logger.info("Using RPi.GPIO backend for unknown SOC")
            else:
                self.gpio_backend = SimulatedGPIOBackend()
                if self.logger:
                    self.logger.warning("Using simulated GPIO backend")

    def _get_generic_pin_mapping(self) -> Dict[str, int]:
        """Get generic pin mapping for unknown SOCs"""
        return {
            "status_led_green": 7,
            "status_led_red": 11,
            "status_led_blue": 13,
            "reset_button": 15,
            "config_button": 16,
            "i2c_sda": 3,
            "i2c_scl": 5,
            "spi_mosi": 19,
            "spi_miso": 21,
            "spi_sclk": 23,
            "spi_ce0": 24,
            "pwm0": 12,
            "pwm1": 33,
        }

    def _initialize_gpio(self) -> None:
        """Initialize GPIO pins based on SOC configuration"""
        if not self.gpio_backend:
            return

        try:
            # Setup status LEDs as outputs
            for led in ["status_led_green", "status_led_red", "status_led_blue"]:
                if led in self.pin_mapping:
                    pin = self.pin_mapping[led]
                    if self.gpio_backend.setup_pin(pin, "output"):
                        # Turn off LED initially
                        self.gpio_backend.write_pin(pin, False)

            # Setup buttons as inputs with pull-up
            for button in ["reset_button", "config_button"]:
                if button in self.pin_mapping:
                    pin = self.pin_mapping[button]
                    self.gpio_backend.setup_pin(pin, "input", "up")

            self.initialized = True
            if self.logger:
                self.logger.info("GPIO initialization completed successfully")

        except Exception as e:
            if self.logger:
                self.logger.error(f"GPIO initialization failed: {e}")
            self.initialized = False

    def set_led(self, led_name: str, state: bool) -> Result[bool, Exception]:
        """Set LED state"""
        if not self.initialized or not self.gpio_backend:
            return Result.failure(
                SystemError(
                    ErrorCode.SYSTEM_NOT_INITIALIZED,
                    "GPIO service not initialized",
                    ErrorSeverity.MEDIUM,
                )
            )

        if led_name not in self.pin_mapping:
            return Result.failure(
                SystemError(
                    ErrorCode.INVALID_PARAMETER,
                    f"Unknown LED: {led_name}",
                    ErrorSeverity.LOW,
                )
            )

        try:
            pin = self.pin_mapping[led_name]
            success = self.gpio_backend.write_pin(pin, state)
            if success:
                return Result.success(True)
            else:
                return Result.failure(
                    SystemError(
                        ErrorCode.GPIO_OPERATION_FAILED,
                        f"Failed to set LED {led_name}",
                        ErrorSeverity.MEDIUM,
                    )
                )
        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.GPIO_OPERATION_FAILED,
                    f"Error setting LED {led_name}: {e}",
                    ErrorSeverity.MEDIUM,
                )
            )

    def read_button(self, button_name: str) -> Result[bool, Exception]:
        """Read button state"""
        if not self.initialized or not self.gpio_backend:
            return Result.failure(
                SystemError(
                    ErrorCode.SYSTEM_NOT_INITIALIZED,
                    "GPIO service not initialized",
                    ErrorSeverity.MEDIUM,
                )
            )

        if button_name not in self.pin_mapping:
            return Result.failure(
                SystemError(
                    ErrorCode.INVALID_PARAMETER,
                    f"Unknown button: {button_name}",
                    ErrorSeverity.LOW,
                )
            )

        try:
            pin = self.pin_mapping[button_name]
            # Button is pressed when pin reads LOW (due to pull-up)
            state = not self.gpio_backend.read_pin(pin)
            return Result.success(state)
        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.GPIO_OPERATION_FAILED,
                    f"Error reading button {button_name}: {e}",
                    ErrorSeverity.MEDIUM,
                )
            )

    def setup_pwm(self, pwm_name: str, frequency: int) -> Result[Any, Exception]:
        """Setup PWM on specified pin"""
        if not self.initialized or not self.gpio_backend:
            return Result.failure(
                SystemError(
                    ErrorCode.SYSTEM_NOT_INITIALIZED,
                    "GPIO service not initialized",
                    ErrorSeverity.MEDIUM,
                )
            )

        if pwm_name not in self.pin_mapping:
            return Result.failure(
                SystemError(
                    ErrorCode.INVALID_PARAMETER,
                    f"Unknown PWM pin: {pwm_name}",
                    ErrorSeverity.LOW,
                )
            )

        try:
            pin = self.pin_mapping[pwm_name]
            pwm_instance = self.gpio_backend.setup_pwm(pin, frequency)
            if pwm_instance:
                self.pwm_instances[pwm_name] = pwm_instance
                return Result.success(pwm_instance)
            else:
                return Result.failure(
                    SystemError(
                        ErrorCode.GPIO_OPERATION_FAILED,
                        f"Failed to setup PWM on {pwm_name}",
                        ErrorSeverity.MEDIUM,
                    )
                )
        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.GPIO_OPERATION_FAILED,
                    f"Error setting up PWM {pwm_name}: {e}",
                    ErrorSeverity.MEDIUM,
                )
            )

    def get_soc_info(self) -> Dict[str, Any]:
        """Get SOC information"""
        if not self.soc_spec:
            return {"soc": "unknown", "family": "unknown"}

        return {
            "soc": self.soc_spec.name,
            "family": self.soc_spec.family.value,
            "architecture": self.soc_spec.architecture.value,
            "gpio_pins": self.soc_spec.io.gpio_pins,
            "available_pins": list(self.pin_mapping.keys()),
        }

    def get_pin_mapping(self) -> Dict[str, int]:
        """Get current pin mapping"""
        return self.pin_mapping.copy()

    def add_custom_pin(self, name: str, pin: int) -> Result[bool, Exception]:
        """Add custom pin mapping"""
        if name in self.pin_mapping:
            return Result.failure(
                SystemError(
                    ErrorCode.INVALID_PARAMETER,
                    f"Pin name already exists: {name}",
                    ErrorSeverity.LOW,
                )
            )

        # Validate pin number based on SOC capabilities
        if self.soc_spec and pin > self.soc_spec.io.gpio_pins:
            return Result.failure(
                SystemError(
                    ErrorCode.INVALID_PARAMETER,
                    f"Pin {pin} exceeds SOC GPIO count ({self.soc_spec.io.gpio_pins})",
                    ErrorSeverity.LOW,
                )
            )

        self.pin_mapping[name] = pin
        return Result.success(True)

    def cleanup(self) -> None:
        """Cleanup GPIO resources"""
        # Stop all PWM instances
        for pwm in self.pwm_instances.values():
            try:
                if hasattr(pwm, "stop"):
                    pwm.stop()
            except Exception:
                pass
        self.pwm_instances.clear()

        # Cleanup GPIO backend
        if self.gpio_backend:
            self.gpio_backend.cleanup()

        self.initialized = False
        if self.logger:
            self.logger.info("GPIO cleanup completed")

    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup()


# Backward compatibility alias
RockPi4BPlusGPIOService = DynamicGPIOService
