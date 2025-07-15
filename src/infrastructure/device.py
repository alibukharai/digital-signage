"""
Device information provider implementation with improved error handling
"""

import json
import subprocess
import uuid
from typing import Optional

from ..common.result_handling import Result
from ..domain.errors import ErrorCode, ErrorSeverity, SystemError
from ..interfaces import DeviceInfo, IDeviceInfoProvider, ILogger


class DeviceInfoProvider(IDeviceInfoProvider):
    """Concrete implementation of device info provider"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self._device_info: Optional[DeviceInfo] = None
        self._device_id: Optional[str] = None
        self._mac_address: Optional[str] = None

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
        """Get provisioning code for QR"""
        device_id = self.get_device_id()
        mac = self.get_mac_address()
        # Create a simple provisioning code
        return f"ROCKPI:{device_id}:{mac.replace(':', '')}"

    def _collect_device_info(self) -> DeviceInfo:
        """Collect comprehensive device information with consistent error handling"""
        try:
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
            hardware_version = (
                hardware_version_result.value
                if hardware_version_result.is_success()
                else "Unknown"
            )
            firmware_version = (
                firmware_version_result.value
                if firmware_version_result.is_success()
                else "Unknown"
            )
            capabilities = (
                capabilities_result.value
                if capabilities_result.is_success()
                else ["wifi", "bluetooth"]
            )

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
        """Get hardware version information"""
        try:
            # Try to get board information for Rock Pi
            board_info = []

            # Check device tree model
            try:
                with open("/proc/device-tree/model", "r") as f:
                    model = f.read().strip().replace("\x00", "")
                    if model:
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

            return "Rock Pi 3399"

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

    def _get_capabilities(self) -> list[str]:
        """Get device capabilities"""
        capabilities = []

        # Check for WiFi capability
        try:
            result = subprocess.run(
                ["nmcli", "device", "status"], capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                if "wifi" in result.stdout.lower():
                    capabilities.append("wifi")
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ) as e:
            if self.logger:
                self.logger.debug(f"WiFi capability check failed: {e}")
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Unexpected error checking WiFi capability: {e}")

        # Check for Bluetooth capability
        try:
            result = subprocess.run(
                ["hciconfig"], capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0 and "hci" in result.stdout:
                capabilities.append("bluetooth")
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ) as e:
            if self.logger:
                self.logger.debug(f"Bluetooth capability check failed: {e}")
        except Exception as e:
            if self.logger:
                self.logger.warning(
                    f"Unexpected error checking Bluetooth capability: {e}"
                )

        # Check for Ethernet capability
        try:
            result = subprocess.run(
                ["ip", "link", "show"], capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                if any(iface in result.stdout for iface in ["eth", "enp", "eno"]):
                    capabilities.append("ethernet")
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ) as e:
            if self.logger:
                self.logger.debug(f"Ethernet capability check failed: {e}")
        except Exception as e:
            if self.logger:
                self.logger.warning(
                    f"Unexpected error checking Ethernet capability: {e}"
                )

        # Check for display capability
        try:
            import os

            if os.environ.get("DISPLAY") or os.path.exists("/dev/fb0"):
                capabilities.append("display")
        except (OSError, PermissionError) as e:
            if self.logger:
                self.logger.debug(f"Display capability check failed: {e}")
        except Exception as e:
            if self.logger:
                self.logger.warning(
                    f"Unexpected error checking display capability: {e}"
                )
            pass

        # Default capabilities for Rock Pi 3399
        if not capabilities:
            capabilities = ["wifi", "bluetooth", "ethernet", "display"]

        return capabilities

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
