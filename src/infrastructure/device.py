"""
Device information provider implementation with SOC-aware hardware detection
"""

import json
import subprocess
import uuid
from typing import Optional

from ..common.result_handling import Result
from ..domain.errors import ErrorCode, ErrorSeverity, SystemError
from ..domain.soc_specifications import SOCSpecification, soc_manager
from ..interfaces import DeviceInfo, IDeviceInfoProvider, ILogger


class DeviceInfoProvider(IDeviceInfoProvider):
    """Concrete implementation of device info provider with SOC awareness"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self._device_info: Optional[DeviceInfo] = None
        self._device_id: Optional[str] = None
        self._mac_address: Optional[str] = None
        self._soc_spec: Optional[SOCSpecification] = None

    def get_device_info(self) -> DeviceInfo:
        """Get comprehensive device information"""
        if self._device_info is None:
            self._device_info = self._collect_device_info()
        return self._device_info

    def get_device_id(self) -> str:
        """Get unique device identifier"""
        if self._device_id is None:
            self._device_id = self._generate_device_id()
        return self._device_id

    def get_mac_address(self) -> str:
        """Get device MAC address"""
        if self._mac_address is None:
            self._mac_address = self._get_mac_address()
        return self._mac_address

    def get_provisioning_code(self) -> str:
        """Get provisioning code for QR based on SOC type"""
        device_id = self.get_device_id()
        mac = self.get_mac_address()
        soc_spec = self._get_soc_spec()

        # Create SOC-aware provisioning code
        if soc_spec:
            if soc_spec.name == "OP1":
                prefix = "ROCKPI4B+"
            elif soc_spec.name == "RK3399":
                prefix = "ROCKPI4"
            elif soc_spec.family.value == "broadcom":
                prefix = "RASPI"
            elif soc_spec.family.value == "allwinner":
                prefix = "ORANGEPI"
            else:
                prefix = f"BOARD-{soc_spec.name}"
        else:
            prefix = "DEVICE"

        return f"{prefix}:{device_id}:{mac.replace(':', '')}"

    def _get_soc_spec(self) -> Optional[SOCSpecification]:
        """Get SOC specification (cached)"""
        if self._soc_spec is None:
            self._soc_spec = soc_manager.detect_soc()
        return self._soc_spec

    def _collect_device_info(self) -> DeviceInfo:
        """Collect comprehensive device information with SOC-aware detection"""
        try:
            # Get SOC specification first
            soc_spec = self._get_soc_spec()

            # Use Result pattern internally for consistent error handling
            device_id_result = self._generate_device_id_safe()
            mac_address_result = self._get_mac_address_safe()
            hardware_version_result = self._get_hardware_version_safe()
            firmware_version_result = self._get_firmware_version_safe()
            capabilities_result = self._get_capabilities_safe()

            # Handle any failures by falling back to defaults or raising with context
            device_id = (
                device_id_result.value if device_id_result.is_success() else "UNKNOWN"
            )
            mac_address = (
                mac_address_result.value
                if mac_address_result.is_success()
                else "00:00:00:00:00:00"
            )

            # Enhanced hardware version with SOC detection
            if hardware_version_result.is_success():
                if soc_spec:
                    hardware_version = (
                        f"{hardware_version_result.value} ({soc_spec.name})"
                    )
                else:
                    hardware_version = hardware_version_result.value
            else:
                if soc_spec:
                    hardware_version = f"{soc_spec.name} Board"
                else:
                    hardware_version = "Unknown Board"

            firmware_version = (
                firmware_version_result.value
                if firmware_version_result.is_success()
                else "Unknown"
            )

            # Enhanced capabilities using SOC specifications
            if capabilities_result.is_success():
                capabilities = capabilities_result.value
            else:
                capabilities = (
                    self._get_capabilities_from_soc(soc_spec) if soc_spec else []
                )

            # Log SOC detection results
            if self.logger and soc_spec:
                self.logger.info(
                    f"Detected SOC: {soc_spec.name} ({soc_spec.family.value})"
                )
                self.logger.info(f"Architecture: {soc_spec.architecture.value}")
                self.logger.info(f"CPU Cores: {soc_spec.performance.cpu_cores}")
                self.logger.info(f"Memory Max: {soc_spec.performance.memory_max_gb}GB")
                self.logger.info(f"GPIO Pins: {soc_spec.io.gpio_pins}")

            # Log any failures for debugging
            for result, name in [
                (device_id_result, "device_id"),
                (mac_address_result, "mac_address"),
                (hardware_version_result, "hardware_version"),
                (firmware_version_result, "firmware_version"),
                (capabilities_result, "capabilities"),
            ]:
                if result.is_failure() and self.logger:
                    self.logger.warning(f"Failed to get {name}: {result.error}")

            return DeviceInfo(
                device_id=device_id,
                mac_address=mac_address,
                hardware_version=hardware_version,
                firmware_version=firmware_version,
                capabilities=capabilities,
            )

        except Exception as e:
            error_msg = f"Critical failure collecting device info: {e}"
            if self.logger:
                self.logger.error(error_msg)
            raise SystemError(
                ErrorCode.DEVICE_INFO_UNAVAILABLE,
                error_msg,
                ErrorSeverity.HIGH,
            )

    def _generate_device_id(self) -> str:
        """Generate or retrieve persistent device ID"""
        try:
            # Try to get machine ID from systemd
            try:
                with open("/etc/machine-id", "r") as f:
                    machine_id = f.read().strip()
                    if machine_id:
                        return machine_id[:8].upper()  # Use first 8 chars
            except FileNotFoundError:
                pass

            # Fallback to DMI product UUID
            try:
                with open("/sys/class/dmi/id/product_uuid", "r") as f:
                    product_uuid = f.read().strip()
                    if product_uuid:
                        return product_uuid.split("-")[0].upper()
            except FileNotFoundError:
                pass

            # Last resort: generate from MAC address
            mac = self._get_mac_address()
            if mac:
                return mac.replace(":", "")[-8:].upper()

            # Ultimate fallback: random UUID
            return str(uuid.uuid4()).split("-")[0].upper()

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Device ID generation fallback: {e}")
            return str(uuid.uuid4()).split("-")[0].upper()

    def _generate_device_id_safe(self) -> Result[str, Exception]:
        """Generate device ID using Result pattern for consistent error handling"""
        try:
            device_id = self._generate_device_id()
            return Result.success(device_id)
        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.DEVICE_INFO_UNAVAILABLE,
                    f"Failed to generate device ID: {e}",
                    ErrorSeverity.MEDIUM,
                )
            )

    def _get_mac_address(self) -> str:
        """Get MAC address of primary network interface"""
        try:
            # Try to get WiFi interface MAC
            for interface in ["wlan0", "wlp3s0", "wlo1"]:
                try:
                    with open(f"/sys/class/net/{interface}/address", "r") as f:
                        mac = f.read().strip()
                        if mac and mac != "00:00:00:00:00:00":
                            return mac.upper()
                except FileNotFoundError:
                    continue

            # Fallback to ethernet interface
            for interface in ["eth0", "enp2s0", "eno1"]:
                try:
                    with open(f"/sys/class/net/{interface}/address", "r") as f:
                        mac = f.read().strip()
                        if mac and mac != "00:00:00:00:00:00":
                            return mac.upper()
                except FileNotFoundError:
                    continue

            # Use ip command as fallback
            result = subprocess.run(
                ["ip", "link", "show"], capture_output=True, text=True
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "link/ether" in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == "link/ether" and i + 1 < len(parts):
                                mac = parts[i + 1]
                                if mac != "00:00:00:00:00:00":
                                    return mac.upper()

            # Final fallback
            return "00:00:00:00:00:00"

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to get MAC address: {e}")
            return "00:00:00:00:00:00"

    def _get_mac_address_safe(self) -> Result[str, Exception]:
        """Get MAC address using Result pattern for consistent error handling"""
        try:
            mac_address = self._get_mac_address()
            if mac_address == "00:00:00:00:00:00":
                return Result.failure(
                    SystemError(
                        ErrorCode.DEVICE_INFO_UNAVAILABLE,
                        "No valid MAC address found",
                        ErrorSeverity.MEDIUM,
                    )
                )
            return Result.success(mac_address)
        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.DEVICE_INFO_UNAVAILABLE,
                    f"Failed to get MAC address: {e}",
                    ErrorSeverity.MEDIUM,
                )
            )

    def _get_hardware_version(self) -> str:
        """Get hardware version information with ROCK Pi 4B+ detection"""
        try:
            # Try to get board information for Rock Pi
            board_info = []

            # Check device tree model first (most reliable for ARM boards)
            try:
                with open("/proc/device-tree/model", "r") as f:
                    model = f.read().strip().replace("\x00", "")
                    if model:
                        board_info.append(model)
            except FileNotFoundError:
                pass

            # Check firmware devicetree model
            try:
                with open("/sys/firmware/devicetree/base/model", "r") as f:
                    model = f.read().strip().replace("\x00", "")
                    if model and model not in board_info:
                        board_info.append(model)
            except FileNotFoundError:
                pass

            # Check DMI board name
            try:
                with open("/sys/class/dmi/id/board_name", "r") as f:
                    board_name = f.read().strip()
                    if board_name and board_name != "To be filled by O.E.M.":
                        board_info.append(board_name)
            except FileNotFoundError:
                pass

            # Check DMI product name
            try:
                with open("/sys/class/dmi/id/product_name", "r") as f:
                    product = f.read().strip()
                    if product and product != "To be filled by O.E.M.":
                        board_info.append(product)
            except FileNotFoundError:
                pass

            if board_info:
                return " / ".join(board_info)

            # Fallback based on SoC detection
            soc_type = self._detect_soc_type()
            if soc_type == "OP1":
                return "ROCK Pi 4B Plus"
            elif soc_type == "RK3399":
                return "ROCK Pi 4 (RK3399)"
            else:
                return "Unknown ARM Board"

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to get hardware version: {e}")
            return "Unknown"

    def _get_hardware_version_safe(self) -> Result[str, Exception]:
        """Get hardware version using Result pattern for consistent error handling"""
        try:
            hardware_version = self._get_hardware_version()
            return Result.success(hardware_version)
        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.DEVICE_INFO_UNAVAILABLE,
                    f"Failed to get hardware version: {e}",
                    ErrorSeverity.LOW,
                )
            )

    def _get_firmware_version(self) -> str:
        """Get firmware/kernel version"""
        try:
            with open("/proc/version", "r") as f:
                version = f.read().strip()
                # Extract kernel version
                parts = version.split()
                if len(parts) >= 3:
                    return parts[2]
            return "Unknown"
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to get firmware version: {e}")
            return "Unknown"

    def _get_firmware_version_safe(self) -> Result[str, Exception]:
        """Get firmware version using Result pattern for consistent error handling"""
        try:
            firmware_version = self._get_firmware_version()
            return Result.success(firmware_version)
        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.DEVICE_INFO_UNAVAILABLE,
                    f"Failed to get firmware version: {e}",
                    ErrorSeverity.LOW,
                )
            )

    def _get_capabilities_from_soc(self, soc_spec: SOCSpecification) -> list[str]:
        """Get capabilities based on SOC specification"""
        capabilities = []

        # Add connectivity capabilities
        if "802.11" in " ".join(soc_spec.connectivity.wifi_standards):
            capabilities.append("wifi")
            if "802.11ac" in soc_spec.connectivity.wifi_standards:
                capabilities.append("wifi_ac")
            if "802.11ax" in soc_spec.connectivity.wifi_standards:
                capabilities.append("wifi_6")

        if soc_spec.connectivity.bluetooth_version != "unknown":
            capabilities.append("bluetooth")
            if soc_spec.connectivity.bluetooth_version.startswith("5"):
                capabilities.append("bluetooth_5_0")
            elif soc_spec.connectivity.bluetooth_version.startswith("4"):
                capabilities.append("bluetooth_4_0")

        if soc_spec.connectivity.ethernet_speeds:
            capabilities.append("ethernet")
            if "1000" in soc_spec.connectivity.ethernet_speeds:
                capabilities.append("gigabit_ethernet")
            if "2500" in soc_spec.connectivity.ethernet_speeds:
                capabilities.append("2_5g_ethernet")

        # Add display capabilities
        if soc_spec.connectivity.display_outputs > 0:
            capabilities.append("display")
            if "4K" in soc_spec.connectivity.max_resolution:
                capabilities.append("4k_display")
            if soc_spec.connectivity.hdmi_version == "2.0":
                capabilities.append("hdmi_2_0")
            elif soc_spec.connectivity.hdmi_version == "2.1":
                capabilities.append("hdmi_2_1")

        # Add USB capabilities
        usb_ports = soc_spec.connectivity.usb_ports
        if usb_ports.get("usb2", 0) > 0:
            capabilities.append("usb_2_0")
        if usb_ports.get("usb3", 0) > 0:
            capabilities.append("usb_3_0")
        if usb_ports.get("usb_otg", 0) > 0:
            capabilities.append("usb_otg")

        # Add IO capabilities
        if soc_spec.io.gpio_pins > 0:
            capabilities.append("gpio")
            if soc_spec.io.gpio_pins >= 40:
                capabilities.append("gpio_40_pin")

        if soc_spec.io.i2c_buses > 0:
            capabilities.append("i2c")
        if soc_spec.io.spi_buses > 0:
            capabilities.append("spi")
        if soc_spec.io.uart_ports > 0:
            capabilities.append("uart")
        if soc_spec.io.pwm_channels > 0:
            capabilities.append("pwm")
        if soc_spec.io.adc_channels > 0:
            capabilities.append("adc")

        # Add storage capabilities
        if soc_spec.io.emmc_support:
            capabilities.append("emmc")
        if soc_spec.io.sd_card_support:
            capabilities.append("sd_card")
        if soc_spec.io.nvme_support:
            capabilities.append("nvme_support")
        if soc_spec.io.sata_support:
            capabilities.append("sata")

        # Add power capabilities
        if soc_spec.power.poe_support:
            capabilities.append("poe_capable")
        if soc_spec.power.battery_support:
            capabilities.append("battery_support")

        # Add performance indicators
        if soc_spec.performance.cpu_cores >= 6:
            capabilities.append("hexa_core")
        elif soc_spec.performance.cpu_cores >= 4:
            capabilities.append("quad_core")

        if soc_spec.performance.cpu_big_cores > 0:
            capabilities.append("big_little_cpu")

        if soc_spec.performance.memory_max_gb >= 8:
            capabilities.append("high_memory")
        elif soc_spec.performance.memory_max_gb >= 4:
            capabilities.append("mid_memory")

        return capabilities

    def _get_capabilities(self) -> list[str]:
        """Get device capabilities with SOC-aware detection and runtime verification"""
        # Start with SOC-based capabilities
        soc_spec = self._get_soc_spec()
        if soc_spec:
            capabilities = self._get_capabilities_from_soc(soc_spec)
        else:
            capabilities = []

        # Verify and enhance with runtime detection
        self._verify_wifi_capabilities(capabilities)
        self._verify_bluetooth_capabilities(capabilities)
        self._verify_ethernet_capabilities(capabilities)
        self._verify_display_capabilities(capabilities)
        self._verify_storage_capabilities(capabilities)
        self._verify_gpio_capabilities(capabilities)

        return capabilities

    def _verify_wifi_capabilities(self, capabilities: list[str]) -> None:
        """Verify WiFi capabilities at runtime"""
        try:
            result = subprocess.run(
                ["nmcli", "device", "status"], capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                if "wifi" in result.stdout.lower():
                    if "wifi" not in capabilities:
                        capabilities.append("wifi")

                    # Check for 802.11ac support
                    try:
                        iw_result = subprocess.run(
                            ["iw", "list"], capture_output=True, text=True, timeout=5
                        )
                        if "802.11ac" in iw_result.stdout:
                            if "wifi_ac" not in capabilities:
                                capabilities.append("wifi_ac")
                        if "802.11ax" in iw_result.stdout:
                            if "wifi_6" not in capabilities:
                                capabilities.append("wifi_6")
                    except (subprocess.SubprocessError, FileNotFoundError):
                        pass
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ) as e:
            if self.logger:
                self.logger.debug(f"WiFi capability verification failed: {e}")

    def _verify_bluetooth_capabilities(self, capabilities: list[str]) -> None:
        """Verify Bluetooth capabilities at runtime"""
        try:
            result = subprocess.run(
                ["hciconfig"], capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0 and "hci" in result.stdout:
                if "bluetooth" not in capabilities:
                    capabilities.append("bluetooth")

                # Try to detect actual BT version from hciconfig
                try:
                    if "Version: 5." in result.stdout:
                        if "bluetooth_5_0" not in capabilities:
                            capabilities.append("bluetooth_5_0")
                    elif "LMP Version: 5." in result.stdout:
                        if "bluetooth_5_0" not in capabilities:
                            capabilities.append("bluetooth_5_0")
                    elif "Version: 4." in result.stdout:
                        if "bluetooth_4_0" not in capabilities:
                            capabilities.append("bluetooth_4_0")
                except Exception:
                    pass

        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ) as e:
            if self.logger:
                self.logger.debug(f"Bluetooth capability verification failed: {e}")

    def _verify_ethernet_capabilities(self, capabilities: list[str]) -> None:
        """Verify Ethernet capabilities at runtime"""
        try:
            result = subprocess.run(
                ["ip", "link", "show"], capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                if any(iface in result.stdout for iface in ["eth", "enp", "eno"]):
                    if "ethernet" not in capabilities:
                        capabilities.append("ethernet")

                    # Try to detect speed capability
                    try:
                        # Check ethtool for actual interface speed support
                        for line in result.stdout.split("\n"):
                            if "eth" in line or "enp" in line or "eno" in line:
                                interface = line.split(":")[1].strip().split("@")[0]
                                ethtool_result = subprocess.run(
                                    ["ethtool", interface],
                                    capture_output=True,
                                    text=True,
                                    timeout=5,
                                )
                                if "1000baseT" in ethtool_result.stdout:
                                    if "gigabit_ethernet" not in capabilities:
                                        capabilities.append("gigabit_ethernet")
                                break
                    except (subprocess.SubprocessError, FileNotFoundError):
                        pass

        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ) as e:
            if self.logger:
                self.logger.debug(f"Ethernet capability verification failed: {e}")

    def _verify_display_capabilities(self, capabilities: list[str]) -> None:
        """Verify display capabilities at runtime"""
        try:
            import os

            if os.environ.get("DISPLAY") or os.path.exists("/dev/fb0"):
                if "display" not in capabilities:
                    capabilities.append("display")

                # Try to detect actual display resolution capabilities
                try:
                    xrandr_result = subprocess.run(
                        ["xrandr", "--query"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if "3840x2160" in xrandr_result.stdout:
                        if "4k_detected" not in capabilities:
                            capabilities.append("4k_detected")
                    if "1920x1080" in xrandr_result.stdout:
                        if "1080p_detected" not in capabilities:
                            capabilities.append("1080p_detected")
                except (subprocess.SubprocessError, FileNotFoundError):
                    pass

        except Exception as e:
            if self.logger:
                self.logger.debug(f"Display capability verification failed: {e}")

    def _verify_storage_capabilities(self, capabilities: list[str]) -> None:
        """Verify storage capabilities at runtime"""
        try:
            import os

            # Check for eMMC
            if os.path.exists("/dev/mmcblk1"):
                if "emmc_detected" not in capabilities:
                    capabilities.append("emmc_detected")

            # Check for SD card
            if os.path.exists("/dev/mmcblk0"):
                if "sd_card_detected" not in capabilities:
                    capabilities.append("sd_card_detected")

            # Check for NVMe
            if os.path.exists("/dev/nvme0n1"):
                if "nvme_detected" not in capabilities:
                    capabilities.append("nvme_detected")

            # Check for SATA
            sata_devices = [f"/dev/sd{chr(ord('a') + i)}" for i in range(8)]
            for device in sata_devices:
                if os.path.exists(device):
                    if "sata_detected" not in capabilities:
                        capabilities.append("sata_detected")
                    break

        except Exception as e:
            if self.logger:
                self.logger.debug(f"Storage capability verification failed: {e}")

    def _verify_gpio_capabilities(self, capabilities: list[str]) -> None:
        """Verify GPIO capabilities at runtime"""
        try:
            import os

            # Check for GPIO access
            if os.path.exists("/sys/class/gpio"):
                if "gpio_accessible" not in capabilities:
                    capabilities.append("gpio_accessible")

            # Check for specific GPIO chips (SOC-specific)
            soc_spec = self._get_soc_spec()
            if soc_spec and soc_spec.family.value == "rockchip":
                # Check for Rockchip GPIO chips
                gpio_chips = ["/sys/class/gpio/gpiochip0", "/sys/class/gpio/gpiochip32"]
                for chip in gpio_chips:
                    if os.path.exists(chip):
                        if "rockchip_gpio" not in capabilities:
                            capabilities.append("rockchip_gpio")
                        break
            elif soc_spec and soc_spec.family.value == "broadcom":
                # Check for Broadcom GPIO
                if os.path.exists("/sys/class/gpio/gpiochip0"):
                    if "broadcom_gpio" not in capabilities:
                        capabilities.append("broadcom_gpio")

        except Exception as e:
            if self.logger:
                self.logger.debug(f"GPIO capability verification failed: {e}")

    def _get_capabilities_safe(self) -> Result[list[str], Exception]:
        """Get device capabilities using Result pattern for consistent error handling"""
        try:
            capabilities = self._get_capabilities()
            return Result.success(capabilities)
        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.DEVICE_INFO_UNAVAILABLE,
                    f"Failed to get device capabilities: {e}",
                    ErrorSeverity.LOW,
                )
            )

    def _detect_soc_type(self) -> str:
        """Enhanced SoC detection for ROCK PI variants"""
        try:
            # Check for OP1 (ROCK PI 4B+)
            with open("/proc/device-tree/compatible", "r") as f:
                compatible = f.read().strip()
                if "rockchip,op1" in compatible or "rockchip,rk3399-op1" in compatible:
                    return "OP1"
                elif "rockchip,rk3399" in compatible:
                    return "RK3399"

            # Fallback: Check CPU info
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read()
                if "OP1" in cpuinfo:
                    return "OP1"

            # Check specific ROCK PI 4B+ identifiers
            try:
                with open("/sys/firmware/devicetree/base/model", "r") as f:
                    model = f.read().strip()
                    if "ROCK Pi 4B Plus" in model or "ROCK Pi 4A Plus" in model:
                        return "OP1"
            except FileNotFoundError:
                pass

            return "RK3399"  # Default fallback
        except Exception as e:
            if self.logger:
                self.logger.warning(f"SoC detection failed: {e}")
            return "UNKNOWN"

    def _get_memory_info(self) -> dict:
        """Get detailed memory information for OP1"""
        try:
            memory_info = {}

            # Get total memory
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        memory_info["total_kb"] = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        memory_info["available_kb"] = int(line.split()[1])

            # Detect LPDDR4 configuration
            try:
                # Check for LPDDR4 specific information
                result = subprocess.run(
                    ["dmidecode", "-t", "memory"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if "LPDDR4" in result.stdout:
                    memory_info["type"] = "LPDDR4"
                    memory_info["dual_channel"] = True
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

            return memory_info
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Memory detection failed: {e}")
            return {"type": "Unknown", "total_kb": 0}

    def _get_default_capabilities(self, soc_type: str) -> list[str]:
        """Get default capabilities based on SoC type"""
        if soc_type == "OP1":
            return [
                "wifi",
                "bluetooth_5_0",
                "ethernet",
                "display",
                "hdmi_2_0",
                "4k_display",
                "gpio",
                "i2c",
                "spi",
                "uart",
                "poe_capable",
                "usb_3_0",
                "emmc",
                "nvme",
            ]
        elif soc_type == "RK3399":
            return [
                "wifi",
                "bluetooth",
                "ethernet",
                "display",
                "hdmi",
                "gpio",
                "i2c",
                "spi",
                "uart",
                "usb_3_0",
                "emmc",
            ]
        else:
            return ["ethernet", "display", "gpio"]

    def configure_memory_optimization(self) -> bool:
        """Configure memory settings optimized for OP1 LPDDR4"""
        try:
            memory_info = self._get_memory_info()
            total_memory = memory_info.get("total_kb", 1024 * 1024)  # Default 1GB

            # Optimize for LPDDR4 dual-channel
            optimizations = {
                # Reduce swappiness for better performance with LPDDR4
                "/proc/sys/vm/swappiness": "10",
                # Optimize for dual-channel memory access
                "/proc/sys/vm/vfs_cache_pressure": "50",
                # Better memory reclaim for embedded systems
                "/proc/sys/vm/min_free_kbytes": str(min(65536, total_memory // 32)),
            }

            applied_count = 0
            for path, value in optimizations.items():
                try:
                    with open(path, "w") as f:
                        f.write(value)
                    if self.logger:
                        self.logger.info(
                            f"Applied memory optimization: {path} = {value}"
                        )
                    applied_count += 1
                except PermissionError:
                    if self.logger:
                        self.logger.warning(
                            f"Cannot write to {path}, run as root for optimization"
                        )
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"Failed to optimize {path}: {e}")

            return applied_count > 0

        except Exception as e:
            if self.logger:
                self.logger.error(f"Memory optimization failed: {e}")
            return False
