"""
Base types and data classes for SOC specifications
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


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