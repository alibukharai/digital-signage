"""
Device information provider implementation
"""

import json
import subprocess
import uuid
from typing import Optional

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
        """Collect comprehensive device information"""
        try:
            device_id = self.get_device_id()
            mac_address = self.get_mac_address()
            hardware_version = self._get_hardware_version()
            firmware_version = self._get_firmware_version()
            capabilities = self._get_capabilities()

            return DeviceInfo(
                device_id=device_id,
                mac_address=mac_address,
                hardware_version=hardware_version,
                firmware_version=firmware_version,
                capabilities=capabilities,
            )

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to collect device info: {e}")
            raise SystemError(
                ErrorCode.DEVICE_INFO_UNAVAILABLE,
                f"Cannot collect device information: {str(e)}",
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

    def _get_capabilities(self) -> list[str]:
        """Get device capabilities"""
        capabilities = []

        # Check for WiFi capability
        try:
            result = subprocess.run(
                ["nmcli", "device", "status"], capture_output=True, text=True
            )

            if result.returncode == 0:
                if "wifi" in result.stdout.lower():
                    capabilities.append("wifi")
        except Exception:
            pass

        # Check for Bluetooth capability
        try:
            result = subprocess.run(["hciconfig"], capture_output=True, text=True)

            if result.returncode == 0 and "hci" in result.stdout:
                capabilities.append("bluetooth")
        except Exception:
            pass

        # Check for Ethernet capability
        try:
            result = subprocess.run(
                ["ip", "link", "show"], capture_output=True, text=True
            )

            if result.returncode == 0:
                if any(iface in result.stdout for iface in ["eth", "enp", "eno"]):
                    capabilities.append("ethernet")
        except Exception:
            pass

        # Check for display capability
        try:
            import os

            if os.environ.get("DISPLAY") or os.path.exists("/dev/fb0"):
                capabilities.append("display")
        except Exception:
            pass

        # Default capabilities for Rock Pi 3399
        if not capabilities:
            capabilities = ["wifi", "bluetooth", "ethernet", "display"]

        return capabilities
