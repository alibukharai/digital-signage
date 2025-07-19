"""
Device hardware detection and SOC identification
"""

import subprocess
from typing import Optional

from ...common.result_handling import Result
from ...domain.errors import ErrorCode, ErrorSeverity, SystemError
try:
    from ...domain.soc_specifications import SOCSpecification, soc_manager
except ImportError:
    # Fallback if SOC specifications are not available
    SOCSpecification = None
    soc_manager = None
from ...interfaces import ILogger


class DeviceDetector:
    """Hardware detection and SOC identification service"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self._soc_spec: Optional["SOCSpecification"] = None

    def get_soc_spec(self) -> Optional["SOCSpecification"]:
        """Get SOC specification (cached)"""
        if self._soc_spec is None and soc_manager is not None:
            self._soc_spec = soc_manager.detect_soc()
        return self._soc_spec

    def get_hardware_version(self) -> Result[str, Exception]:
        """Get hardware version with SOC-aware detection"""
        try:
            soc_spec = self.get_soc_spec()
            
            # Try different methods based on SOC type
            if soc_spec and hasattr(soc_spec, 'name') and soc_spec.name in ["OP1", "RK3399"]:
                return self._get_rockpi_hardware_version()
            elif soc_spec and hasattr(soc_spec, 'family') and hasattr(soc_spec.family, 'value') and soc_spec.family.value == "broadcom":
                return self._get_raspberry_pi_hardware_version()
            else:
                return self._get_generic_hardware_version()
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Hardware version detection failed: {e}")
            return Result.failure(
                SystemError(
                    message=f"Hardware version detection failed: {e}",
                    error_code=ErrorCode.HARDWARE_ERROR,
                    severity=ErrorSeverity.HIGH,
                )
            )

    def _get_rockpi_hardware_version(self) -> Result[str, Exception]:
        """Get ROCK Pi specific hardware version"""
        try:
            # Try device tree compatible string first
            try:
                with open("/proc/device-tree/compatible", "r") as f:
                    compatible = f.read().strip('\x00')
                    if "rockchip,rk3399" in compatible:
                        return Result.success("ROCK Pi 4B+")
            except FileNotFoundError:
                pass

            # Try board name from DMI
            try:
                with open("/sys/class/dmi/id/board_name", "r") as f:
                    board_name = f.read().strip()
                    if board_name:
                        return Result.success(f"ROCK Pi {board_name}")
            except FileNotFoundError:
                pass

            # Try product name
            try:
                with open("/sys/class/dmi/id/product_name", "r") as f:
                    product_name = f.read().strip()
                    if product_name:
                        return Result.success(product_name)
            except FileNotFoundError:
                pass

            return Result.success("ROCK Pi 4 (Unknown variant)")

        except Exception as e:
            return Result.failure(e)

    def _get_raspberry_pi_hardware_version(self) -> Result[str, Exception]:
        """Get Raspberry Pi specific hardware version"""
        try:
            # Try CPU info for Pi revision
            try:
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if line.startswith("Revision"):
                            revision = line.split(":")[1].strip()
                            return Result.success(f"Raspberry Pi (Rev: {revision})")
            except FileNotFoundError:
                pass

            # Try device tree model
            try:
                with open("/proc/device-tree/model", "r") as f:
                    model = f.read().strip('\x00')
                    if model:
                        return Result.success(model)
            except FileNotFoundError:
                pass

            return Result.success("Raspberry Pi (Unknown model)")

        except Exception as e:
            return Result.failure(e)

    def _get_generic_hardware_version(self) -> Result[str, Exception]:
        """Get generic hardware version for other platforms"""
        try:
            # Try DMI information
            dmi_fields = [
                "/sys/class/dmi/id/board_name",
                "/sys/class/dmi/id/product_name",
                "/sys/class/dmi/id/sys_vendor"
            ]

            for field_path in dmi_fields:
                try:
                    with open(field_path, "r") as f:
                        value = f.read().strip()
                        if value and value not in ["To be filled by O.E.M.", "Default string"]:
                            return Result.success(value)
                except FileNotFoundError:
                    continue

            # Try uname as fallback
            try:
                result = subprocess.run(
                    ["uname", "-m"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    machine = result.stdout.strip()
                    return Result.success(f"Generic {machine}")
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass

            return Result.success("Unknown Hardware")

        except Exception as e:
            return Result.failure(e)

    def get_firmware_version(self) -> Result[str, Exception]:
        """Get firmware version with SOC-aware detection"""
        try:
            soc_spec = self.get_soc_spec()
            
            if soc_spec and hasattr(soc_spec, 'name') and soc_spec.name in ["OP1", "RK3399"]:
                return self._get_rockpi_firmware_version()
            elif soc_spec and hasattr(soc_spec, 'family') and hasattr(soc_spec.family, 'value') and soc_spec.family.value == "broadcom":
                return self._get_raspberry_pi_firmware_version()
            else:
                return self._get_generic_firmware_version()
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Firmware version detection failed: {e}")
            return Result.failure(
                SystemError(
                    message=f"Firmware version detection failed: {e}",
                    error_code=ErrorCode.HARDWARE_ERROR,
                    severity=ErrorSeverity.MEDIUM,
                )
            )

    def _get_rockpi_firmware_version(self) -> Result[str, Exception]:
        """Get ROCK Pi specific firmware version"""
        try:
            # Try u-boot version
            try:
                result = subprocess.run(
                    ["dmesg", "|", "grep", "U-Boot"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    shell=True
                )
                if result.returncode == 0 and result.stdout:
                    uboot_line = result.stdout.split('\n')[0]
                    return Result.success(f"U-Boot: {uboot_line}")
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass

            # Try BIOS version from DMI
            try:
                with open("/sys/class/dmi/id/bios_version", "r") as f:
                    bios_version = f.read().strip()
                    if bios_version:
                        return Result.success(f"BIOS: {bios_version}")
            except FileNotFoundError:
                pass

            return Result.success("Unknown Firmware")

        except Exception as e:
            return Result.failure(e)

    def _get_raspberry_pi_firmware_version(self) -> Result[str, Exception]:
        """Get Raspberry Pi specific firmware version"""
        try:
            # Try vcgencmd for firmware version
            try:
                result = subprocess.run(
                    ["vcgencmd", "version"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return Result.success(result.stdout.strip())
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
                pass

            return Result.success("Unknown Pi Firmware")

        except Exception as e:
            return Result.failure(e)

    def _get_generic_firmware_version(self) -> Result[str, Exception]:
        """Get generic firmware version"""
        try:
            # Try DMI BIOS information
            try:
                with open("/sys/class/dmi/id/bios_version", "r") as f:
                    bios_version = f.read().strip()
                    if bios_version:
                        return Result.success(f"BIOS: {bios_version}")
            except FileNotFoundError:
                pass

            # Try kernel version as fallback
            try:
                result = subprocess.run(
                    ["uname", "-r"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    kernel_version = result.stdout.strip()
                    return Result.success(f"Kernel: {kernel_version}")
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass

            return Result.success("Unknown Firmware")

        except Exception as e:
            return Result.failure(e)

    def get_capabilities(self) -> Result[dict, Exception]:
        """Get device capabilities based on SOC specification"""
        try:
            soc_spec = self.get_soc_spec()
            capabilities = {
                "wifi": True,  # Assume WiFi is available
                "bluetooth": True,  # Assume Bluetooth is available
                "ethernet": True,  # Assume Ethernet is available
                "gpio": False,
                "4k_display": False,
                "hw_acceleration": False,
            }

            if soc_spec:
                # SOC-specific capabilities
                if soc_spec.name in ["OP1", "RK3399"]:
                    capabilities.update({
                        "gpio": True,
                        "4k_display": True,
                        "hw_acceleration": True,
                        "usb3": True,
                        "pcie": True,
                    })
                elif soc_spec.family.value == "broadcom":
                    capabilities.update({
                        "gpio": True,
                        "camera": True,
                        "dsi_display": True,
                    })

            return Result.success(capabilities)

        except Exception as e:
            if self.logger:
                self.logger.error(f"Capability detection failed: {e}")
            return Result.failure(
                SystemError(
                    message=f"Capability detection failed: {e}",
                    error_code=ErrorCode.HARDWARE_ERROR,
                    severity=ErrorSeverity.LOW,
                )
            )