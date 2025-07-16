"""
SOC Specifications and Hardware Abstraction Layer
Provides dynamic SOC detection and hardware-specific configurations
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class SOCFamily(Enum):
    """Supported SOC families"""

    ROCKCHIP = "rockchip"
    ALLWINNER = "allwinner"
    BROADCOM = "broadcom"
    QUALCOMM = "qualcomm"
    MEDIATEK = "mediatek"
    UNKNOWN = "unknown"


class ArchitectureType(Enum):
    """CPU architectures"""

    ARM64 = "aarch64"
    ARM32 = "armv7l"
    X86_64 = "x86_64"
    X86 = "i386"


@dataclass
class PerformanceProfile:
    """Performance characteristics of a SOC"""

    cpu_cores: int
    cpu_big_cores: int = 0
    cpu_little_cores: int = 0
    cpu_max_freq_mhz: int = 0
    cpu_big_max_freq_mhz: int = 0
    cpu_little_max_freq_mhz: int = 0
    gpu_cores: int = 0
    gpu_max_freq_mhz: int = 0
    memory_max_gb: int = 0
    memory_type: str = "unknown"
    thermal_design_power: int = 0  # TDP in watts


@dataclass
class ConnectivityProfile:
    """Connectivity capabilities of a SOC"""

    wifi_standards: List[str] = field(default_factory=list)
    bluetooth_version: str = "unknown"
    ethernet_speeds: List[str] = field(default_factory=list)
    usb_ports: Dict[str, int] = field(default_factory=dict)  # {"usb2": 2, "usb3": 2}
    hdmi_version: str = "unknown"
    max_resolution: str = "1080p"
    display_outputs: int = 1
    audio_outputs: List[str] = field(default_factory=list)


@dataclass
class IOProfile:
    """Input/Output capabilities"""

    gpio_pins: int = 0
    i2c_buses: int = 0
    spi_buses: int = 0
    uart_ports: int = 0
    pwm_channels: int = 0
    adc_channels: int = 0
    can_buses: int = 0
    pcie_lanes: int = 0
    emmc_support: bool = False
    sd_card_support: bool = False
    nvme_support: bool = False
    sata_support: bool = False


@dataclass
class PowerProfile:
    """Power management capabilities"""

    poe_support: bool = False
    battery_support: bool = False
    power_states: List[str] = field(default_factory=list)
    voltage_rails: List[str] = field(default_factory=list)
    current_monitoring: bool = False
    temperature_sensors: int = 0


@dataclass
class SOCSpecification:
    """Complete SOC specification"""

    name: str
    family: SOCFamily
    architecture: ArchitectureType
    part_number: str = ""
    revision: str = ""
    manufacturer: str = ""
    performance: PerformanceProfile = field(default_factory=PerformanceProfile)
    connectivity: ConnectivityProfile = field(default_factory=ConnectivityProfile)
    io: IOProfile = field(default_factory=IOProfile)
    power: PowerProfile = field(default_factory=PowerProfile)
    detection_patterns: List[str] = field(default_factory=list)
    gpio_mapping: Dict[str, int] = field(default_factory=dict)
    pin_mapping: Dict[str, Dict] = field(
        default_factory=dict
    )  # Detailed pin configurations
    boot_optimization: Dict[str, Any] = field(default_factory=dict)

    def get_device_tree_compatible(self) -> List[str]:
        """Get device tree compatible strings for this SOC"""
        compatibles = []
        if self.family == SOCFamily.ROCKCHIP:
            compatibles.append(f"rockchip,{self.part_number.lower()}")
        elif self.family == SOCFamily.ALLWINNER:
            compatibles.append(f"allwinner,{self.part_number.lower()}")
        elif self.family == SOCFamily.BROADCOM:
            compatibles.append(f"brcm,{self.part_number.lower()}")
        return compatibles


class SOCDetector(ABC):
    """Abstract base class for SOC detection"""

    @abstractmethod
    def detect(self) -> Optional[SOCSpecification]:
        """Detect SOC and return specification"""
        pass

    @abstractmethod
    def get_supported_socs(self) -> List[str]:
        """Get list of supported SOC names"""
        pass


class RockchipDetector(SOCDetector):
    """Rockchip SOC family detector"""

    ROCKCHIP_SOCS = {
        "rk3399": {
            "name": "RK3399",
            "part_number": "RK3399",
            "performance": PerformanceProfile(
                cpu_cores=6,
                cpu_big_cores=2,
                cpu_little_cores=4,
                cpu_big_max_freq_mhz=2000,
                cpu_little_max_freq_mhz=1500,
                gpu_cores=4,
                gpu_max_freq_mhz=800,
                memory_max_gb=4,
                memory_type="lpddr4",
                thermal_design_power=15,
            ),
            "connectivity": ConnectivityProfile(
                wifi_standards=["802.11ac", "802.11n"],
                bluetooth_version="4.2",
                ethernet_speeds=["1000"],
                usb_ports={"usb2": 2, "usb3": 2},
                hdmi_version="2.0",
                max_resolution="4K@60Hz",
                display_outputs=2,
                audio_outputs=["hdmi", "i2s", "spdif"],
            ),
            "io": IOProfile(
                gpio_pins=40,
                i2c_buses=8,
                spi_buses=6,
                uart_ports=5,
                pwm_channels=4,
                adc_channels=6,
                pcie_lanes=4,
                emmc_support=True,
                sd_card_support=True,
                nvme_support=True,
            ),
            "detection_patterns": [
                r"rk3399",
                r"rockchip.*rk3399",
                r"rock.*pi.*4",
                r"nanopi.*m4",
            ],
        },
        "op1": {  # Optimized Process 1 (Enhanced RK3399)
            "name": "OP1",
            "part_number": "OP1",
            "performance": PerformanceProfile(
                cpu_cores=6,
                cpu_big_cores=2,
                cpu_little_cores=4,
                cpu_big_max_freq_mhz=2000,
                cpu_little_max_freq_mhz=1500,
                gpu_cores=4,
                gpu_max_freq_mhz=800,
                memory_max_gb=8,  # Enhanced memory support
                memory_type="lpddr4x",
                thermal_design_power=12,  # Optimized power consumption
            ),
            "connectivity": ConnectivityProfile(
                wifi_standards=["802.11ac", "802.11ax"],  # Enhanced WiFi
                bluetooth_version="5.0",  # Enhanced Bluetooth
                ethernet_speeds=["1000"],
                usb_ports={"usb2": 2, "usb3": 2, "usb_otg": 1},
                hdmi_version="2.1",  # Enhanced HDMI
                max_resolution="4K@120Hz",
                display_outputs=2,
                audio_outputs=["hdmi", "i2s", "spdif", "pdm"],
            ),
            "io": IOProfile(
                gpio_pins=40,
                i2c_buses=8,
                spi_buses=6,
                uart_ports=5,
                pwm_channels=4,
                adc_channels=6,
                pcie_lanes=4,
                emmc_support=True,
                sd_card_support=True,
                nvme_support=True,
            ),
            "power": PowerProfile(
                poe_support=True,  # PoE capability
                power_states=["active", "idle", "suspend", "standby"],
                voltage_rails=["5v", "3v3", "1v8", "1v2"],
                current_monitoring=True,
                temperature_sensors=3,
            ),
            "detection_patterns": [
                r"op1",
                r"rock.*pi.*4b.*plus",
                r"optimized.*process.*1",
            ],
        },
        "rk3588": {
            "name": "RK3588",
            "part_number": "RK3588",
            "performance": PerformanceProfile(
                cpu_cores=8,
                cpu_big_cores=4,
                cpu_little_cores=4,
                cpu_big_max_freq_mhz=2400,
                cpu_little_max_freq_mhz=1800,
                gpu_cores=4,
                gpu_max_freq_mhz=1000,
                memory_max_gb=32,
                memory_type="lpddr4x",
                thermal_design_power=25,
            ),
            "connectivity": ConnectivityProfile(
                wifi_standards=["802.11ax"],
                bluetooth_version="5.2",
                ethernet_speeds=["2500", "1000"],
                usb_ports={"usb2": 2, "usb3": 4},
                hdmi_version="2.1",
                max_resolution="8K@60Hz",
                display_outputs=4,
            ),
            "detection_patterns": [r"rk3588", r"rock.*5"],
        },
    }

    def detect(self) -> Optional[SOCSpecification]:
        """Detect Rockchip SOC"""
        try:
            # Check device tree model
            device_info = self._get_device_info()

            for soc_key, soc_data in self.ROCKCHIP_SOCS.items():
                for pattern in soc_data["detection_patterns"]:
                    if re.search(pattern, device_info, re.IGNORECASE):
                        return self._build_soc_spec(soc_key, soc_data)

            return None

        except Exception:
            return None

    def _get_device_info(self) -> str:
        """Get device information for detection"""
        info_sources = [
            "/proc/device-tree/model",
            "/sys/firmware/devicetree/base/model",
            "/proc/cpuinfo",
            "/sys/class/dmi/id/board_name",
            "/sys/class/dmi/id/product_name",
        ]

        device_info = ""
        for source in info_sources:
            try:
                with open(source, "r") as f:
                    content = f.read().strip().replace("\x00", "")
                    device_info += f" {content}"
            except (FileNotFoundError, PermissionError):
                continue

        return device_info.lower()

    def _build_soc_spec(self, soc_key: str, soc_data: Dict) -> SOCSpecification:
        """Build SOC specification from data"""
        spec = SOCSpecification(
            name=soc_data["name"],
            family=SOCFamily.ROCKCHIP,
            architecture=ArchitectureType.ARM64,
            part_number=soc_data["part_number"],
            manufacturer="Rockchip",
            performance=soc_data["performance"],
            connectivity=soc_data["connectivity"],
            io=soc_data.get("io", IOProfile()),
            power=soc_data.get("power", PowerProfile()),
            detection_patterns=soc_data["detection_patterns"],
        )

        # Add SOC-specific GPIO mapping
        if soc_key in ["rk3399", "op1"]:
            spec.gpio_mapping = self._get_rockpi_gpio_mapping()
            spec.pin_mapping = self._get_rockpi_pin_mapping()

        return spec

    def _get_rockpi_gpio_mapping(self) -> Dict[str, int]:
        """Get ROCK Pi GPIO mapping"""
        return {
            # Status LEDs
            "status_led_green": 7,
            "status_led_red": 11,
            "status_led_blue": 13,
            # Buttons
            "reset_button": 15,
            "config_button": 16,
            # Communication interfaces
            "i2c_sda": 3,
            "i2c_scl": 5,
            "spi_mosi": 19,
            "spi_miso": 21,
            "spi_sclk": 23,
            "spi_ce0": 24,
            # PWM
            "pwm0": 12,
            "pwm1": 33,
            # Extra GPIO
            "gpio_5": 29,
            "gpio_6": 31,
            "gpio_12": 32,
            "gpio_19": 35,
            "gpio_16": 36,
            "gpio_26": 37,
            "gpio_20": 38,
            "gpio_21": 40,
        }

    def _get_rockpi_pin_mapping(self) -> Dict[str, Dict]:
        """Get detailed pin mapping with capabilities"""
        return {
            "3": {"gpio": 2, "function": "i2c_sda", "voltage": "3v3"},
            "5": {"gpio": 3, "function": "i2c_scl", "voltage": "3v3"},
            "7": {"gpio": 4, "function": "gpio", "voltage": "3v3"},
            "11": {"gpio": 17, "function": "gpio", "voltage": "3v3"},
            "12": {"gpio": 18, "function": "pwm", "voltage": "3v3"},
            "13": {"gpio": 27, "function": "gpio", "voltage": "3v3"},
            "15": {"gpio": 22, "function": "gpio", "voltage": "3v3"},
            "16": {"gpio": 23, "function": "gpio", "voltage": "3v3"},
            "19": {"gpio": 10, "function": "spi_mosi", "voltage": "3v3"},
            "21": {"gpio": 9, "function": "spi_miso", "voltage": "3v3"},
            "23": {"gpio": 11, "function": "spi_sclk", "voltage": "3v3"},
            "24": {"gpio": 8, "function": "spi_ce0", "voltage": "3v3"},
            "29": {"gpio": 5, "function": "gpio", "voltage": "3v3"},
            "31": {"gpio": 6, "function": "gpio", "voltage": "3v3"},
            "32": {"gpio": 12, "function": "gpio", "voltage": "3v3"},
            "33": {"gpio": 13, "function": "pwm", "voltage": "3v3"},
            "35": {"gpio": 19, "function": "gpio", "voltage": "3v3"},
            "36": {"gpio": 16, "function": "gpio", "voltage": "3v3"},
            "37": {"gpio": 26, "function": "gpio", "voltage": "3v3"},
            "38": {"gpio": 20, "function": "gpio", "voltage": "3v3"},
            "40": {"gpio": 21, "function": "gpio", "voltage": "3v3"},
        }

    def get_supported_socs(self) -> List[str]:
        """Get supported Rockchip SOCs"""
        return list(self.ROCKCHIP_SOCS.keys())


class AllwinnerDetector(SOCDetector):
    """Allwinner SOC family detector"""

    ALLWINNER_SOCS = {
        "h6": {
            "name": "H6",
            "part_number": "H6",
            "performance": PerformanceProfile(
                cpu_cores=4,
                cpu_max_freq_mhz=1800,
                gpu_cores=2,
                memory_max_gb=4,
                memory_type="lpddr3",
            ),
            "connectivity": ConnectivityProfile(
                wifi_standards=["802.11ac"],
                bluetooth_version="4.2",
                ethernet_speeds=["1000"],
                usb_ports={"usb2": 2, "usb3": 1},
                hdmi_version="2.0",
                max_resolution="4K@60Hz",
            ),
            "detection_patterns": [r"allwinner.*h6", r"orange.*pi.*3"],
        },
        "h616": {
            "name": "H616",
            "part_number": "H616",
            "performance": PerformanceProfile(
                cpu_cores=4,
                cpu_max_freq_mhz=1800,
                gpu_cores=1,
                memory_max_gb=4,
                memory_type="lpddr4",
            ),
            "connectivity": ConnectivityProfile(
                wifi_standards=["802.11n"],
                bluetooth_version="4.0",
                ethernet_speeds=["1000"],
                usb_ports={"usb2": 3, "usb3": 0},
                hdmi_version="2.0",
                max_resolution="4K@30Hz",
            ),
            "detection_patterns": [r"allwinner.*h616", r"orange.*pi.*zero.*2"],
        },
        "h618": {
            "name": "H618",
            "part_number": "H618",
            "performance": PerformanceProfile(
                cpu_cores=4,
                cpu_max_freq_mhz=1500,
                gpu_cores=1,
                memory_max_gb=4,
                memory_type="lpddr4",
            ),
            "connectivity": ConnectivityProfile(
                wifi_standards=["802.11ac"],
                bluetooth_version="5.0",
                ethernet_speeds=["1000"],
                usb_ports={"usb2": 2, "usb3": 1},
                hdmi_version="2.0",
                max_resolution="4K@60Hz",
            ),
            "detection_patterns": [r"allwinner.*h618", r"orange.*pi.*5"],
        },
        "a64": {
            "name": "A64",
            "part_number": "A64",
            "performance": PerformanceProfile(
                cpu_cores=4,
                cpu_max_freq_mhz=1200,
                memory_max_gb=2,
                memory_type="lpddr3",
            ),
            "detection_patterns": [r"allwinner.*a64", r"pine64"],
        },
    }

    def detect(self) -> Optional[SOCSpecification]:
        """Detect Allwinner SOC"""
        try:
            # Check device tree model
            device_info = self._get_device_info()

            for soc_key, soc_data in self.ALLWINNER_SOCS.items():
                for pattern in soc_data["detection_patterns"]:
                    if re.search(pattern, device_info, re.IGNORECASE):
                        return self._build_soc_spec(soc_key, soc_data)

            return None

        except Exception:
            return None

    def _get_device_info(self) -> str:
        """Get device information for detection"""
        info_sources = [
            "/proc/device-tree/model",
            "/sys/firmware/devicetree/base/model",
            "/proc/cpuinfo",
            "/sys/class/dmi/id/board_name",
            "/sys/class/dmi/id/product_name",
        ]

        device_info = ""
        for source in info_sources:
            try:
                with open(source, "r") as f:
                    content = f.read().strip().replace("\x00", "")
                    device_info += f" {content}"
            except (FileNotFoundError, PermissionError):
                continue

        return device_info.lower()

    def _build_soc_spec(self, soc_key: str, soc_data: Dict) -> SOCSpecification:
        """Build SOC specification from data"""
        spec = SOCSpecification(
            name=soc_data["name"],
            family=SOCFamily.ALLWINNER,
            architecture=ArchitectureType.ARM64,
            part_number=soc_data["part_number"],
            manufacturer="Allwinner",
            performance=soc_data["performance"],
            connectivity=soc_data.get("connectivity", ConnectivityProfile()),
            io=soc_data.get("io", IOProfile()),
            power=soc_data.get("power", PowerProfile()),
            detection_patterns=soc_data["detection_patterns"],
        )

        # Add SOC-specific GPIO mapping for Orange Pi boards
        if soc_key in ["h6", "a64", "h616", "h618"]:
            spec.gpio_mapping = self._get_orangepi_gpio_mapping()
            spec.pin_mapping = self._get_orangepi_pin_mapping()

        return spec

    def _get_orangepi_gpio_mapping(self) -> Dict[str, int]:
        """Get Orange Pi GPIO mapping"""
        return {
            # Status LEDs
            "status_led_green": 7,
            "status_led_red": 11,
            "status_led_blue": 13,
            # Buttons
            "reset_button": 15,
            "config_button": 16,
            # Communication interfaces
            "i2c_sda": 3,
            "i2c_scl": 5,
            "spi_mosi": 19,
            "spi_miso": 21,
            "spi_sclk": 23,
            "spi_ce0": 24,
            # PWM
            "pwm0": 12,
            "pwm1": 33,
            # Extra GPIO
            "gpio_5": 29,
            "gpio_6": 31,
            "gpio_12": 32,
            "gpio_19": 35,
            "gpio_16": 36,
            "gpio_26": 37,
            "gpio_20": 38,
            "gpio_21": 40,
        }

    def _get_orangepi_pin_mapping(self) -> Dict[str, Dict]:
        """Get detailed Orange Pi pin mapping with capabilities"""
        return {
            "3": {"gpio": 2, "function": "i2c_sda", "voltage": "3v3"},
            "5": {"gpio": 3, "function": "i2c_scl", "voltage": "3v3"},
            "7": {"gpio": 4, "function": "gpio", "voltage": "3v3"},
            "11": {"gpio": 17, "function": "gpio", "voltage": "3v3"},
            "12": {"gpio": 18, "function": "pwm", "voltage": "3v3"},
            "13": {"gpio": 27, "function": "gpio", "voltage": "3v3"},
            "15": {"gpio": 22, "function": "gpio", "voltage": "3v3"},
            "16": {"gpio": 23, "function": "gpio", "voltage": "3v3"},
            "19": {"gpio": 10, "function": "spi_mosi", "voltage": "3v3"},
            "21": {"gpio": 9, "function": "spi_miso", "voltage": "3v3"},
            "23": {"gpio": 11, "function": "spi_sclk", "voltage": "3v3"},
            "24": {"gpio": 8, "function": "spi_ce0", "voltage": "3v3"},
            "29": {"gpio": 5, "function": "gpio", "voltage": "3v3"},
            "31": {"gpio": 6, "function": "gpio", "voltage": "3v3"},
            "32": {"gpio": 12, "function": "gpio", "voltage": "3v3"},
            "33": {"gpio": 13, "function": "pwm", "voltage": "3v3"},
            "35": {"gpio": 19, "function": "gpio", "voltage": "3v3"},
            "36": {"gpio": 16, "function": "gpio", "voltage": "3v3"},
            "37": {"gpio": 26, "function": "gpio", "voltage": "3v3"},
            "38": {"gpio": 20, "function": "gpio", "voltage": "3v3"},
            "40": {"gpio": 21, "function": "gpio", "voltage": "3v3"},
        }

    def get_supported_socs(self) -> List[str]:
        """Get supported Allwinner SOCs"""
        return list(self.ALLWINNER_SOCS.keys())


class BroadcomDetector(SOCDetector):
    """Broadcom SOC family detector (Raspberry Pi)"""

    BROADCOM_SOCS = {
        "bcm2835": {
            "name": "BCM2835",
            "part_number": "BCM2835",
            "performance": PerformanceProfile(
                cpu_cores=1, cpu_max_freq_mhz=700, memory_max_gb=1, memory_type="lpddr2"
            ),
            "detection_patterns": [r"bcm2835", r"raspberry.*pi.*1"],
        },
        "bcm2711": {
            "name": "BCM2711",
            "part_number": "BCM2711",
            "performance": PerformanceProfile(
                cpu_cores=4,
                cpu_max_freq_mhz=1500,
                memory_max_gb=8,
                memory_type="lpddr4",
            ),
            "connectivity": ConnectivityProfile(
                wifi_standards=["802.11ac"],
                bluetooth_version="5.0",
                ethernet_speeds=["1000"],
                usb_ports={"usb2": 2, "usb3": 2},
                hdmi_version="2.0",
            ),
            "io": IOProfile(
                gpio_pins=40, i2c_buses=2, spi_buses=2, uart_ports=2, pwm_channels=2
            ),
            "detection_patterns": [r"bcm2711", r"raspberry.*pi.*4"],
        },
        "bcm2712": {
            "name": "BCM2712",
            "part_number": "BCM2712",
            "performance": PerformanceProfile(
                cpu_cores=4,
                cpu_max_freq_mhz=2400,
                memory_max_gb=8,
                memory_type="lpddr4x",
            ),
            "connectivity": ConnectivityProfile(
                wifi_standards=["802.11ac", "802.11ax"],
                bluetooth_version="5.0",
                ethernet_speeds=["1000"],
                usb_ports={"usb2": 2, "usb3": 2},
                hdmi_version="2.1",
                max_resolution="4K@60Hz",
                display_outputs=2,
            ),
            "io": IOProfile(
                gpio_pins=40,
                i2c_buses=2,
                spi_buses=2,
                uart_ports=2,
                pwm_channels=4,
                pcie_lanes=1,
            ),
            "detection_patterns": [r"bcm2712", r"raspberry.*pi.*5"],
        },
    }

    def detect(self) -> Optional[SOCSpecification]:
        """Detect Broadcom SOC"""
        try:
            # Check device tree model
            device_info = self._get_device_info()

            for soc_key, soc_data in self.BROADCOM_SOCS.items():
                for pattern in soc_data["detection_patterns"]:
                    if re.search(pattern, device_info, re.IGNORECASE):
                        return self._build_soc_spec(soc_key, soc_data)

            return None

        except Exception:
            return None

    def _get_device_info(self) -> str:
        """Get device information for detection"""
        info_sources = [
            "/proc/device-tree/model",
            "/sys/firmware/devicetree/base/model",
            "/proc/cpuinfo",
            "/sys/class/dmi/id/board_name",
            "/sys/class/dmi/id/product_name",
        ]

        device_info = ""
        for source in info_sources:
            try:
                with open(source, "r") as f:
                    content = f.read().strip().replace("\x00", "")
                    device_info += f" {content}"
            except (FileNotFoundError, PermissionError):
                continue

        return device_info.lower()

    def _build_soc_spec(self, soc_key: str, soc_data: Dict) -> SOCSpecification:
        """Build SOC specification from data"""
        spec = SOCSpecification(
            name=soc_data["name"],
            family=SOCFamily.BROADCOM,
            architecture=ArchitectureType.ARM64
            if soc_key != "bcm2835"
            else ArchitectureType.ARM32,
            part_number=soc_data["part_number"],
            manufacturer="Broadcom",
            performance=soc_data["performance"],
            connectivity=soc_data.get("connectivity", ConnectivityProfile()),
            io=soc_data.get("io", IOProfile()),
            power=soc_data.get("power", PowerProfile()),
            detection_patterns=soc_data["detection_patterns"],
        )

        # Add SOC-specific GPIO mapping for Raspberry Pi boards
        if soc_key in ["bcm2711", "bcm2835", "bcm2712"]:
            spec.gpio_mapping = self._get_raspberry_pi_gpio_mapping()
            spec.pin_mapping = self._get_raspberry_pi_pin_mapping()

        return spec

    def _get_raspberry_pi_gpio_mapping(self) -> Dict[str, int]:
        """Get Raspberry Pi GPIO mapping"""
        return {
            # Status LEDs
            "status_led_green": 7,
            "status_led_red": 11,
            "status_led_blue": 13,
            # Buttons
            "reset_button": 15,
            "config_button": 16,
            # Communication interfaces
            "i2c_sda": 3,
            "i2c_scl": 5,
            "spi_mosi": 19,
            "spi_miso": 21,
            "spi_sclk": 23,
            "spi_ce0": 24,
            # PWM
            "pwm0": 12,
            "pwm1": 33,
            # Extra GPIO
            "gpio_5": 29,
            "gpio_6": 31,
            "gpio_12": 32,
            "gpio_19": 35,
            "gpio_16": 36,
            "gpio_26": 37,
            "gpio_20": 38,
            "gpio_21": 40,
        }

    def _get_raspberry_pi_pin_mapping(self) -> Dict[str, Dict]:
        """Get detailed Raspberry Pi pin mapping with capabilities"""
        return {
            "3": {"gpio": 2, "function": "i2c_sda", "voltage": "3v3"},
            "5": {"gpio": 3, "function": "i2c_scl", "voltage": "3v3"},
            "7": {"gpio": 4, "function": "gpio", "voltage": "3v3"},
            "11": {"gpio": 17, "function": "gpio", "voltage": "3v3"},
            "12": {"gpio": 18, "function": "pwm", "voltage": "3v3"},
            "13": {"gpio": 27, "function": "gpio", "voltage": "3v3"},
            "15": {"gpio": 22, "function": "gpio", "voltage": "3v3"},
            "16": {"gpio": 23, "function": "gpio", "voltage": "3v3"},
            "19": {"gpio": 10, "function": "spi_mosi", "voltage": "3v3"},
            "21": {"gpio": 9, "function": "spi_miso", "voltage": "3v3"},
            "23": {"gpio": 11, "function": "spi_sclk", "voltage": "3v3"},
            "24": {"gpio": 8, "function": "spi_ce0", "voltage": "3v3"},
            "29": {"gpio": 5, "function": "gpio", "voltage": "3v3"},
            "31": {"gpio": 6, "function": "gpio", "voltage": "3v3"},
            "32": {"gpio": 12, "function": "gpio", "voltage": "3v3"},
            "33": {"gpio": 13, "function": "pwm", "voltage": "3v3"},
            "35": {"gpio": 19, "function": "gpio", "voltage": "3v3"},
            "36": {"gpio": 16, "function": "gpio", "voltage": "3v3"},
            "37": {"gpio": 26, "function": "gpio", "voltage": "3v3"},
            "38": {"gpio": 20, "function": "gpio", "voltage": "3v3"},
            "40": {"gpio": 21, "function": "gpio", "voltage": "3v3"},
        }

    def get_supported_socs(self) -> List[str]:
        """Get supported Broadcom SOCs"""
        return list(self.BROADCOM_SOCS.keys())


class MediaTekDetector(SOCDetector):
    """MediaTek SOC family detector"""

    MEDIATEK_SOCS = {
        "mt8183": {
            "name": "MT8183",
            "part_number": "MT8183",
            "performance": PerformanceProfile(
                cpu_cores=8,
                cpu_big_cores=4,
                cpu_little_cores=4,
                cpu_big_max_freq_mhz=2000,
                cpu_little_max_freq_mhz=1400,
                gpu_cores=2,
                memory_max_gb=4,
                memory_type="lpddr4x",
            ),
            "connectivity": ConnectivityProfile(
                wifi_standards=["802.11ac"],
                bluetooth_version="5.0",
                ethernet_speeds=["1000"],
                usb_ports={"usb2": 2, "usb3": 1},
                hdmi_version="2.0",
                max_resolution="4K@30Hz",
            ),
            "detection_patterns": [r"mediatek.*mt8183", r"mt8183"],
        },
        "mt8395": {
            "name": "MT8395",
            "part_number": "MT8395",
            "performance": PerformanceProfile(
                cpu_cores=8,
                cpu_big_cores=4,
                cpu_little_cores=4,
                cpu_big_max_freq_mhz=2200,
                cpu_little_max_freq_mhz=1600,
                gpu_cores=4,
                memory_max_gb=8,
                memory_type="lpddr5",
            ),
            "connectivity": ConnectivityProfile(
                wifi_standards=["802.11ax"],
                bluetooth_version="5.2",
                ethernet_speeds=["2500", "1000"],
                usb_ports={"usb2": 2, "usb3": 2},
                hdmi_version="2.1",
                max_resolution="4K@60Hz",
            ),
            "detection_patterns": [r"mediatek.*mt8395", r"mt8395"],
        },
    }

    def detect(self) -> Optional[SOCSpecification]:
        """Detect MediaTek SOC"""
        try:
            device_info = self._get_device_info()

            for soc_key, soc_data in self.MEDIATEK_SOCS.items():
                for pattern in soc_data["detection_patterns"]:
                    if re.search(pattern, device_info, re.IGNORECASE):
                        return self._build_soc_spec(soc_key, soc_data)

            return None

        except Exception:
            return None

    def _get_device_info(self) -> str:
        """Get device information for detection"""
        info_sources = [
            "/proc/device-tree/model",
            "/sys/firmware/devicetree/base/model",
            "/proc/cpuinfo",
            "/sys/class/dmi/id/board_name",
            "/sys/class/dmi/id/product_name",
        ]

        device_info = ""
        for source in info_sources:
            try:
                with open(source, "r") as f:
                    content = f.read().strip().replace("\x00", "")
                    device_info += f" {content}"
            except (FileNotFoundError, PermissionError):
                continue

        return device_info.lower()

    def _build_soc_spec(self, soc_key: str, soc_data: Dict) -> SOCSpecification:
        """Build SOC specification from data"""
        return SOCSpecification(
            name=soc_data["name"],
            family=SOCFamily.MEDIATEK,
            architecture=ArchitectureType.ARM64,
            part_number=soc_data["part_number"],
            manufacturer="MediaTek",
            performance=soc_data["performance"],
            connectivity=soc_data.get("connectivity", ConnectivityProfile()),
            io=soc_data.get("io", IOProfile()),
            power=soc_data.get("power", PowerProfile()),
            detection_patterns=soc_data["detection_patterns"],
        )

    def get_supported_socs(self) -> List[str]:
        """Get supported MediaTek SOCs"""
        return list(self.MEDIATEK_SOCS.keys())


class QualcommDetector(SOCDetector):
    """Qualcomm SOC family detector"""

    QUALCOMM_SOCS = {
        "qcs605": {
            "name": "QCS605",
            "part_number": "QCS605",
            "performance": PerformanceProfile(
                cpu_cores=8,
                cpu_big_cores=2,
                cpu_little_cores=6,
                cpu_big_max_freq_mhz=1800,
                cpu_little_max_freq_mhz=1600,
                gpu_cores=3,
                memory_max_gb=4,
                memory_type="lpddr4x",
            ),
            "connectivity": ConnectivityProfile(
                wifi_standards=["802.11ac"],
                bluetooth_version="5.0",
                ethernet_speeds=["1000"],
                usb_ports={"usb2": 2, "usb3": 1},
                hdmi_version="2.0",
                max_resolution="4K@30Hz",
            ),
            "detection_patterns": [r"qualcomm.*qcs605", r"qcs605"],
        }
    }

    def detect(self) -> Optional[SOCSpecification]:
        """Detect Qualcomm SOC"""
        try:
            device_info = self._get_device_info()

            for soc_key, soc_data in self.QUALCOMM_SOCS.items():
                for pattern in soc_data["detection_patterns"]:
                    if re.search(pattern, device_info, re.IGNORECASE):
                        return self._build_soc_spec(soc_key, soc_data)

            return None

        except Exception:
            return None

    def _get_device_info(self) -> str:
        """Get device information for detection"""
        info_sources = [
            "/proc/device-tree/model",
            "/sys/firmware/devicetree/base/model",
            "/proc/cpuinfo",
            "/sys/class/dmi/id/board_name",
            "/sys/class/dmi/id/product_name",
        ]

        device_info = ""
        for source in info_sources:
            try:
                with open(source, "r") as f:
                    content = f.read().strip().replace("\x00", "")
                    device_info += f" {content}"
            except (FileNotFoundError, PermissionError):
                continue

        return device_info.lower()

    def _build_soc_spec(self, soc_key: str, soc_data: Dict) -> SOCSpecification:
        """Build SOC specification from data"""
        return SOCSpecification(
            name=soc_data["name"],
            family=SOCFamily.QUALCOMM,
            architecture=ArchitectureType.ARM64,
            part_number=soc_data["part_number"],
            manufacturer="Qualcomm",
            performance=soc_data["performance"],
            connectivity=soc_data.get("connectivity", ConnectivityProfile()),
            io=soc_data.get("io", IOProfile()),
            power=soc_data.get("power", PowerProfile()),
            detection_patterns=soc_data["detection_patterns"],
        )

    def get_supported_socs(self) -> List[str]:
        """Get supported Qualcomm SOCs"""
        return list(self.QUALCOMM_SOCS.keys())


class SOCManager:
    """Central SOC detection and management"""

    def __init__(self):
        # Import here to avoid circular import
        from .soc_registry import soc_registry

        self.detectors = soc_registry.create_all_detectors()
        self._current_soc: Optional[SOCSpecification] = None

    def detect_soc(self) -> Optional[SOCSpecification]:
        """Detect current SOC"""
        if self._current_soc is not None:
            return self._current_soc

        for detector in self.detectors:
            soc_spec = detector.detect()
            if soc_spec is not None:
                self._current_soc = soc_spec
                return soc_spec

        # Return generic fallback
        return self._get_generic_soc()

    def _get_generic_soc(self) -> SOCSpecification:
        """Get generic SOC specification as fallback"""
        return SOCSpecification(
            name="Generic ARM",
            family=SOCFamily.UNKNOWN,
            architecture=ArchitectureType.ARM64,
            part_number="unknown",
            manufacturer="unknown",
            performance=PerformanceProfile(cpu_cores=4),
            connectivity=ConnectivityProfile(),
            io=IOProfile(gpio_pins=40),
            power=PowerProfile(),
        )

    def get_supported_socs(self) -> Dict[str, List[str]]:
        """Get all supported SOCs by family"""
        supported = {}
        for detector in self.detectors:
            family_name = detector.__class__.__name__.replace("Detector", "").lower()
            supported[family_name] = detector.get_supported_socs()
        return supported

    def get_soc_by_name(self, name: str) -> Optional[SOCSpecification]:
        """Get SOC specification by name"""
        name_lower = name.lower()

        for detector in self.detectors:
            if isinstance(detector, RockchipDetector):
                for soc_key, soc_data in detector.ROCKCHIP_SOCS.items():
                    if (
                        soc_key.lower() == name_lower
                        or soc_data["name"].lower() == name_lower
                        or soc_data["part_number"].lower() == name_lower
                    ):
                        return detector._build_soc_spec(soc_key, soc_data)

            elif isinstance(detector, AllwinnerDetector):
                for soc_key, soc_data in detector.ALLWINNER_SOCS.items():
                    if (
                        soc_key.lower() == name_lower
                        or soc_data["name"].lower() == name_lower
                        or soc_data["part_number"].lower() == name_lower
                    ):
                        return detector._build_soc_spec(soc_key, soc_data)

            elif isinstance(detector, BroadcomDetector):
                for soc_key, soc_data in detector.BROADCOM_SOCS.items():
                    if (
                        soc_key.lower() == name_lower
                        or soc_data["name"].lower() == name_lower
                        or soc_data["part_number"].lower() == name_lower
                    ):
                        return detector._build_soc_spec(soc_key, soc_data)

            elif isinstance(detector, MediaTekDetector):
                for soc_key, soc_data in detector.MEDIATEK_SOCS.items():
                    if (
                        soc_key.lower() == name_lower
                        or soc_data["name"].lower() == name_lower
                        or soc_data["part_number"].lower() == name_lower
                    ):
                        return detector._build_soc_spec(soc_key, soc_data)

            elif isinstance(detector, QualcommDetector):
                for soc_key, soc_data in detector.QUALCOMM_SOCS.items():
                    if (
                        soc_key.lower() == name_lower
                        or soc_data["name"].lower() == name_lower
                        or soc_data["part_number"].lower() == name_lower
                    ):
                        return detector._build_soc_spec(soc_key, soc_data)

            elif isinstance(detector, MediaTekDetector):
                for soc_key, soc_data in detector.MEDIATEK_SOCS.items():
                    if (
                        soc_key.lower() == name_lower
                        or soc_data["name"].lower() == name_lower
                        or soc_data["part_number"].lower() == name_lower
                    ):
                        return detector._build_soc_spec(soc_key, soc_data)

            elif isinstance(detector, QualcommDetector):
                for soc_key, soc_data in detector.QUALCOMM_SOCS.items():
                    if (
                        soc_key.lower() == name_lower
                        or soc_data["name"].lower() == name_lower
                        or soc_data["part_number"].lower() == name_lower
                    ):
                        return detector._build_soc_spec(soc_key, soc_data)

        return None

    def add_soc_detector(self, detector: SOCDetector) -> None:
        """Add a new SOC detector to the registry"""
        self.detectors.append(detector)

    def get_all_supported_socs(self) -> List[SOCSpecification]:
        """Get all supported SOC specifications"""
        all_socs = []

        for detector in self.detectors:
            if isinstance(detector, RockchipDetector):
                for soc_key, soc_data in detector.ROCKCHIP_SOCS.items():
                    all_socs.append(detector._build_soc_spec(soc_key, soc_data))

            elif isinstance(detector, AllwinnerDetector):
                for soc_key, soc_data in detector.ALLWINNER_SOCS.items():
                    all_socs.append(detector._build_soc_spec(soc_key, soc_data))

            elif isinstance(detector, BroadcomDetector):
                for soc_key, soc_data in detector.BROADCOM_SOCS.items():
                    all_socs.append(detector._build_soc_spec(soc_key, soc_data))

            elif isinstance(detector, MediaTekDetector):
                for soc_key, soc_data in detector.MEDIATEK_SOCS.items():
                    all_socs.append(detector._build_soc_spec(soc_key, soc_data))

            elif isinstance(detector, QualcommDetector):
                for soc_key, soc_data in detector.QUALCOMM_SOCS.items():
                    all_socs.append(detector._build_soc_spec(soc_key, soc_data))

            elif isinstance(detector, MediaTekDetector):
                for soc_key, soc_data in detector.MEDIATEK_SOCS.items():
                    all_socs.append(detector._build_soc_spec(soc_key, soc_data))

            elif isinstance(detector, QualcommDetector):
                for soc_key, soc_data in detector.QUALCOMM_SOCS.items():
                    all_socs.append(detector._build_soc_spec(soc_key, soc_data))

        return all_socs


# Global SOC manager instance
soc_manager = SOCManager()
