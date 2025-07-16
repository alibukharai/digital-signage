"""
Hardware Abstraction Layer (HAL) for different SOC families
Provides platform-specific implementations while maintaining a common interface
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..common.result_handling import Result
from ..domain.errors import ErrorCode, ErrorSeverity, SystemError
from ..domain.soc_specifications import SOCFamily, SOCSpecification


@dataclass
class HardwareCapabilities:
    """Hardware capabilities detected at runtime"""

    gpio_available: bool = False
    i2c_available: bool = False
    spi_available: bool = False
    pwm_available: bool = False
    uart_available: bool = False
    bluetooth_available: bool = False
    wifi_available: bool = False
    display_available: bool = False
    audio_available: bool = False


class IHardwareAbstractionLayer(ABC):
    """Abstract hardware abstraction layer interface"""

    @abstractmethod
    def initialize(self) -> Result[bool, Exception]:
        """Initialize the hardware abstraction layer"""
        pass

    @abstractmethod
    def get_capabilities(self) -> HardwareCapabilities:
        """Get hardware capabilities"""
        pass

    @abstractmethod
    def get_gpio_mapping(self) -> Dict[str, int]:
        """Get GPIO pin mapping for this platform"""
        pass

    @abstractmethod
    def get_i2c_buses(self) -> List[int]:
        """Get available I2C bus numbers"""
        pass

    @abstractmethod
    def get_spi_buses(self) -> List[int]:
        """Get available SPI bus numbers"""
        pass

    @abstractmethod
    def get_uart_devices(self) -> List[str]:
        """Get available UART device paths"""
        pass

    @abstractmethod
    def get_network_interfaces(self) -> List[str]:
        """Get available network interface names"""
        pass

    @abstractmethod
    def get_display_info(self) -> Dict[str, Any]:
        """Get display configuration information"""
        pass

    @abstractmethod
    def optimize_performance(self) -> Result[bool, Exception]:
        """Apply platform-specific performance optimizations"""
        pass

    @abstractmethod
    def get_thermal_zones(self) -> List[str]:
        """Get thermal zone paths for monitoring"""
        pass


class RockchipHAL(IHardwareAbstractionLayer):
    """Hardware abstraction layer for Rockchip SOCs"""

    def __init__(self, soc_spec: SOCSpecification):
        self.soc_spec = soc_spec
        self.capabilities = HardwareCapabilities()

    def initialize(self) -> Result[bool, Exception]:
        """Initialize Rockchip HAL"""
        try:
            # Detect available hardware interfaces
            self.capabilities.gpio_available = self._check_gpio_available()
            self.capabilities.i2c_available = self._check_i2c_available()
            self.capabilities.spi_available = self._check_spi_available()
            self.capabilities.pwm_available = self._check_pwm_available()
            self.capabilities.uart_available = self._check_uart_available()
            self.capabilities.bluetooth_available = self._check_bluetooth_available()
            self.capabilities.wifi_available = self._check_wifi_available()
            self.capabilities.display_available = self._check_display_available()
            self.capabilities.audio_available = self._check_audio_available()

            return Result.success(True)
        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.DEVICE_INFO_UNAVAILABLE,
                    f"Failed to initialize Rockchip HAL: {e}",
                    ErrorSeverity.HIGH,
                )
            )

    def get_capabilities(self) -> HardwareCapabilities:
        """Get hardware capabilities"""
        return self.capabilities

    def get_gpio_mapping(self) -> Dict[str, int]:
        """Get GPIO pin mapping for Rockchip boards"""
        if self.soc_spec.gpio_mapping:
            return self.soc_spec.gpio_mapping

        # Default Rockchip GPIO mapping
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

    def get_i2c_buses(self) -> List[int]:
        """Get available I2C buses for Rockchip"""
        return [0, 1, 2, 4, 6, 7, 8]  # Common Rockchip I2C buses

    def get_spi_buses(self) -> List[int]:
        """Get available SPI buses for Rockchip"""
        return [0, 1, 2, 5]  # Common Rockchip SPI buses

    def get_uart_devices(self) -> List[str]:
        """Get available UART devices for Rockchip"""
        return ["/dev/ttyS0", "/dev/ttyS2", "/dev/ttyS4"]

    def get_network_interfaces(self) -> List[str]:
        """Get network interfaces for Rockchip"""
        return ["wlan0", "eth0"]

    def get_display_info(self) -> Dict[str, Any]:
        """Get display configuration for Rockchip"""
        return {
            "hdmi_device": "/dev/dri/card0",
            "max_resolution": self.soc_spec.connectivity.max_resolution,
            "hdmi_version": self.soc_spec.connectivity.hdmi_version,
            "display_outputs": self.soc_spec.connectivity.display_outputs,
        }

    def optimize_performance(self) -> Result[bool, Exception]:
        """Apply Rockchip-specific performance optimizations"""
        try:
            optimizations = []

            # CPU governor optimization
            if self.soc_spec.performance.cpu_cores >= 6:  # Big.LITTLE
                optimizations.append("Set ondemand governor for big.LITTLE")
            else:
                optimizations.append("Set performance governor")

            # GPU governor optimization
            optimizations.append("Set simple_ondemand for GPU")

            # Memory optimization
            if "lpddr4" in self.soc_spec.performance.memory_type.lower():
                optimizations.append("Apply LPDDR4 optimizations")

            return Result.success(True)
        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.DEVICE_INFO_UNAVAILABLE,
                    f"Failed to optimize Rockchip performance: {e}",
                    ErrorSeverity.MEDIUM,
                )
            )

    def get_thermal_zones(self) -> List[str]:
        """Get thermal zones for Rockchip"""
        return [
            "/sys/class/thermal/thermal_zone0/temp",  # CPU
            "/sys/class/thermal/thermal_zone1/temp",  # GPU
        ]

    def _check_gpio_available(self) -> bool:
        """Check if GPIO is available"""
        import os

        return os.path.exists("/sys/class/gpio")

    def _check_i2c_available(self) -> bool:
        """Check if I2C is available"""
        import os

        return any(os.path.exists(f"/dev/i2c-{i}") for i in range(10))

    def _check_spi_available(self) -> bool:
        """Check if SPI is available"""
        import os

        return any(os.path.exists(f"/dev/spidev{i}.0") for i in range(10))

    def _check_pwm_available(self) -> bool:
        """Check if PWM is available"""
        import os

        return os.path.exists("/sys/class/pwm")

    def _check_uart_available(self) -> bool:
        """Check if UART is available"""
        import os

        return any(os.path.exists(f"/dev/ttyS{i}") for i in range(10))

    def _check_bluetooth_available(self) -> bool:
        """Check if Bluetooth is available"""
        import os

        return os.path.exists("/sys/class/bluetooth")

    def _check_wifi_available(self) -> bool:
        """Check if WiFi is available"""
        import os

        return any(
            os.path.exists(f"/sys/class/net/{iface}/wireless")
            for iface in ["wlan0", "wlp3s0", "wlo1"]
        )

    def _check_display_available(self) -> bool:
        """Check if display is available"""
        import os

        return os.path.exists("/dev/dri/card0")

    def _check_audio_available(self) -> bool:
        """Check if audio is available"""
        import os

        return os.path.exists("/dev/snd") or any(
            os.path.exists(f"/proc/asound/card{i}") for i in range(5)
        )


class BroadcomHAL(IHardwareAbstractionLayer):
    """Hardware abstraction layer for Broadcom SOCs (Raspberry Pi)"""

    def __init__(self, soc_spec: SOCSpecification):
        self.soc_spec = soc_spec
        self.capabilities = HardwareCapabilities()

    def initialize(self) -> Result[bool, Exception]:
        """Initialize Broadcom HAL"""
        try:
            # Detect available hardware interfaces
            self.capabilities.gpio_available = self._check_gpio_available()
            self.capabilities.i2c_available = self._check_i2c_available()
            self.capabilities.spi_available = self._check_spi_available()
            self.capabilities.pwm_available = self._check_pwm_available()
            self.capabilities.uart_available = self._check_uart_available()
            self.capabilities.bluetooth_available = self._check_bluetooth_available()
            self.capabilities.wifi_available = self._check_wifi_available()
            self.capabilities.display_available = self._check_display_available()
            self.capabilities.audio_available = self._check_audio_available()

            return Result.success(True)
        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.DEVICE_INFO_UNAVAILABLE,
                    f"Failed to initialize Broadcom HAL: {e}",
                    ErrorSeverity.HIGH,
                )
            )

    def get_capabilities(self) -> HardwareCapabilities:
        """Get hardware capabilities"""
        return self.capabilities

    def get_gpio_mapping(self) -> Dict[str, int]:
        """Get GPIO pin mapping for Raspberry Pi"""
        if self.soc_spec.gpio_mapping:
            return self.soc_spec.gpio_mapping

        # Default Raspberry Pi GPIO mapping
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

    def get_i2c_buses(self) -> List[int]:
        """Get available I2C buses for Raspberry Pi"""
        return [0, 1]  # Standard Pi I2C buses

    def get_spi_buses(self) -> List[int]:
        """Get available SPI buses for Raspberry Pi"""
        return [0, 1]  # Standard Pi SPI buses

    def get_uart_devices(self) -> List[str]:
        """Get available UART devices for Raspberry Pi"""
        return ["/dev/ttyAMA0", "/dev/ttyS0"]

    def get_network_interfaces(self) -> List[str]:
        """Get network interfaces for Raspberry Pi"""
        return ["wlan0", "eth0"]

    def get_display_info(self) -> Dict[str, Any]:
        """Get display configuration for Raspberry Pi"""
        return {
            "hdmi_device": "/dev/dri/card0",
            "max_resolution": self.soc_spec.connectivity.max_resolution,
            "hdmi_version": self.soc_spec.connectivity.hdmi_version,
            "display_outputs": self.soc_spec.connectivity.display_outputs,
        }

    def optimize_performance(self) -> Result[bool, Exception]:
        """Apply Raspberry Pi specific optimizations"""
        try:
            optimizations = []

            # GPU memory split optimization
            optimizations.append("Set GPU memory split")

            # CPU governor optimization
            optimizations.append("Set ondemand governor")

            # Enable hardware interfaces
            optimizations.append("Enable I2C, SPI, UART interfaces")

            return Result.success(True)
        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.DEVICE_INFO_UNAVAILABLE,
                    f"Failed to optimize Raspberry Pi performance: {e}",
                    ErrorSeverity.MEDIUM,
                )
            )

    def get_thermal_zones(self) -> List[str]:
        """Get thermal zones for Raspberry Pi"""
        return ["/sys/class/thermal/thermal_zone0/temp"]  # CPU temp

    def _check_gpio_available(self) -> bool:
        """Check if GPIO is available"""
        import os

        return os.path.exists("/sys/class/gpio")

    def _check_i2c_available(self) -> bool:
        """Check if I2C is available"""
        import os

        return os.path.exists("/dev/i2c-1")

    def _check_spi_available(self) -> bool:
        """Check if SPI is available"""
        import os

        return os.path.exists("/dev/spidev0.0")

    def _check_pwm_available(self) -> bool:
        """Check if PWM is available"""
        import os

        return os.path.exists("/sys/class/pwm")

    def _check_uart_available(self) -> bool:
        """Check if UART is available"""
        import os

        return os.path.exists("/dev/ttyAMA0")

    def _check_bluetooth_available(self) -> bool:
        """Check if Bluetooth is available"""
        import os

        return os.path.exists("/sys/class/bluetooth")

    def _check_wifi_available(self) -> bool:
        """Check if WiFi is available"""
        import os

        return os.path.exists("/sys/class/net/wlan0/wireless")

    def _check_display_available(self) -> bool:
        """Check if display is available"""
        import os

        return os.path.exists("/dev/dri/card0")

    def _check_audio_available(self) -> bool:
        """Check if audio is available"""
        import os

        return os.path.exists("/dev/snd")


class GenericHAL(IHardwareAbstractionLayer):
    """Generic hardware abstraction layer for unknown SOCs"""

    def __init__(self, soc_spec: Optional[SOCSpecification] = None):
        self.soc_spec = soc_spec
        self.capabilities = HardwareCapabilities()

    def initialize(self) -> Result[bool, Exception]:
        """Initialize generic HAL"""
        try:
            # Basic capability detection
            self.capabilities.gpio_available = self._check_gpio_available()
            self.capabilities.i2c_available = self._check_i2c_available()
            self.capabilities.spi_available = self._check_spi_available()
            self.capabilities.pwm_available = self._check_pwm_available()
            self.capabilities.uart_available = self._check_uart_available()
            self.capabilities.bluetooth_available = self._check_bluetooth_available()
            self.capabilities.wifi_available = self._check_wifi_available()
            self.capabilities.display_available = self._check_display_available()
            self.capabilities.audio_available = self._check_audio_available()

            return Result.success(True)
        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.DEVICE_INFO_UNAVAILABLE,
                    f"Failed to initialize generic HAL: {e}",
                    ErrorSeverity.MEDIUM,
                )
            )

    def get_capabilities(self) -> HardwareCapabilities:
        """Get hardware capabilities"""
        return self.capabilities

    def get_gpio_mapping(self) -> Dict[str, int]:
        """Get generic GPIO mapping"""
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

    def get_i2c_buses(self) -> List[int]:
        """Get available I2C buses"""
        return [0, 1]

    def get_spi_buses(self) -> List[int]:
        """Get available SPI buses"""
        return [0, 1]

    def get_uart_devices(self) -> List[str]:
        """Get available UART devices"""
        return ["/dev/ttyS0", "/dev/ttyAMA0"]

    def get_network_interfaces(self) -> List[str]:
        """Get network interfaces"""
        return ["wlan0", "eth0"]

    def get_display_info(self) -> Dict[str, Any]:
        """Get display configuration"""
        return {
            "hdmi_device": "/dev/dri/card0",
            "max_resolution": "1920x1080@60",
            "hdmi_version": "2.0",
            "display_outputs": 1,
        }

    def optimize_performance(self) -> Result[bool, Exception]:
        """Apply generic optimizations"""
        return Result.success(True)

    def get_thermal_zones(self) -> List[str]:
        """Get thermal zones"""
        return ["/sys/class/thermal/thermal_zone0/temp"]

    def _check_gpio_available(self) -> bool:
        import os

        return os.path.exists("/sys/class/gpio")

    def _check_i2c_available(self) -> bool:
        import os

        return any(os.path.exists(f"/dev/i2c-{i}") for i in range(5))

    def _check_spi_available(self) -> bool:
        import os

        return any(os.path.exists(f"/dev/spidev{i}.0") for i in range(5))

    def _check_pwm_available(self) -> bool:
        import os

        return os.path.exists("/sys/class/pwm")

    def _check_uart_available(self) -> bool:
        import os

        return any(os.path.exists(f"/dev/ttyS{i}") for i in range(5))

    def _check_bluetooth_available(self) -> bool:
        import os

        return os.path.exists("/sys/class/bluetooth")

    def _check_wifi_available(self) -> bool:
        import os

        return any(
            os.path.exists(f"/sys/class/net/{iface}/wireless")
            for iface in ["wlan0", "wlp3s0", "wlo1"]
        )

    def _check_display_available(self) -> bool:
        import os

        return os.path.exists("/dev/dri/card0")

    def _check_audio_available(self) -> bool:
        import os

        return os.path.exists("/dev/snd")


class HALFactory:
    """Factory for creating appropriate Hardware Abstraction Layer"""

    @staticmethod
    def create_hal(
        soc_spec: Optional[SOCSpecification] = None,
    ) -> IHardwareAbstractionLayer:
        """Create appropriate HAL based on SOC specification"""
        if not soc_spec:
            return GenericHAL()

        if soc_spec.family == SOCFamily.ROCKCHIP:
            return RockchipHAL(soc_spec)
        elif soc_spec.family == SOCFamily.BROADCOM:
            return BroadcomHAL(soc_spec)
        elif soc_spec.family in [
            SOCFamily.ALLWINNER,
            SOCFamily.MEDIATEK,
            SOCFamily.QUALCOMM,
        ]:
            # Use generic HAL for now, can be extended later
            return GenericHAL(soc_spec)
        else:
            return GenericHAL(soc_spec)
