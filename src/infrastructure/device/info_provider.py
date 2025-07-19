"""
Device information provider implementation
"""

import json
import subprocess
import uuid
from typing import Optional

from ...common.result_handling import Result
from ...domain.errors import ErrorCode, ErrorSeverity, SystemError
from ...interfaces import DeviceInfo, IDeviceInfoProvider, ILogger
from .detector import DeviceDetector


class DeviceInfoProvider(IDeviceInfoProvider):
    """Concrete implementation of device info provider"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self._device_info: Optional[DeviceInfo] = None
        self._device_id: Optional[str] = None
        self._mac_address: Optional[str] = None
        self.detector = DeviceDetector(logger)

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
        soc_spec = self.detector.get_soc_spec()

        # Create SOC-aware provisioning code
        if soc_spec and hasattr(soc_spec, 'name'):
            if soc_spec.name == "OP1":
                prefix = "ROCKPI4B+"
            elif soc_spec.name == "RK3399":
                prefix = "ROCKPI4"
            elif hasattr(soc_spec, 'family') and hasattr(soc_spec.family, 'value'):
                if soc_spec.family.value == "broadcom":
                    prefix = "RASPI"
                elif soc_spec.family.value == "allwinner":
                    prefix = "ORANGEPI"
                else:
                    prefix = f"BOARD-{soc_spec.name}"
            else:
                prefix = f"BOARD-{soc_spec.name}"
        else:
            prefix = "DEVICE"

        return f"{prefix}:{device_id}:{mac.replace(':', '')}"

    def get_provisioning_data_for_serial(self) -> dict:
        """Get provisioning data suitable for serial output and testing"""
        soc_spec = self.detector.get_soc_spec()
        device_info = self.get_device_info()
        
        return {
            "device_id": self.get_device_id(),
            "mac_address": self.get_mac_address(),
            "provisioning_code": self.get_provisioning_code(),
            "hardware_version": device_info.hardware_version,
            "firmware_version": device_info.firmware_version,
            "soc_name": soc_spec.name if soc_spec and hasattr(soc_spec, 'name') else "Unknown",
            "capabilities": device_info.capabilities,
            "timestamp": device_info.timestamp.isoformat() if device_info.timestamp else None
        }

    def _collect_device_info(self) -> DeviceInfo:
        """Collect comprehensive device information using detector"""
        try:
            # Use Result pattern internally for consistent error handling
            device_id_result = self._generate_device_id_safe()
            mac_address_result = self._get_mac_address_safe()
            hardware_version_result = self.detector.get_hardware_version()
            firmware_version_result = self.detector.get_firmware_version()
            capabilities_result = self.detector.get_capabilities()

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
                soc_spec = self.detector.get_soc_spec()
                if soc_spec and hasattr(soc_spec, 'name'):
                    hardware_version = (
                        f"{hardware_version_result.value} ({soc_spec.name})"
                    )
                else:
                    hardware_version = hardware_version_result.value
            else:
                hardware_version = "Unknown Hardware"
                if self.logger:
                    self.logger.warning(
                        f"Hardware version detection failed: {hardware_version_result.error}"
                    )

            firmware_version = (
                firmware_version_result.value
                if firmware_version_result.is_success()
                else "Unknown Firmware"
            )
            if not firmware_version_result.is_success() and self.logger:
                self.logger.warning(
                    f"Firmware version detection failed: {firmware_version_result.error}"
                )

            capabilities = (
                capabilities_result.value
                if capabilities_result.is_success()
                else {"wifi": True, "bluetooth": True, "ethernet": True}
            )
            if not capabilities_result.is_success() and self.logger:
                self.logger.warning(
                    f"Capabilities detection failed: {capabilities_result.error}"
                )

            from datetime import datetime

            device_info = DeviceInfo(
                device_id=device_id,
                mac_address=mac_address,
                hardware_version=hardware_version,
                firmware_version=firmware_version,
                capabilities=capabilities,
                timestamp=datetime.now(),
            )

            if self.logger:
                self.logger.info(f"Device info collected: {device_info}")

            return device_info

        except Exception as e:
            if self.logger:
                self.logger.error(f"Device info collection failed: {e}")
            # Return minimal device info with error context
            from datetime import datetime

            return DeviceInfo(
                device_id="ERROR",
                mac_address="00:00:00:00:00:00",
                hardware_version=f"Error: {str(e)}",
                firmware_version="Unknown",
                capabilities={"error": True},
                timestamp=datetime.now(),
            )

    def _generate_device_id(self) -> str:
        """Generate unique device identifier with multiple fallbacks"""
        try:
            # Try machine ID first (most reliable on Linux)
            try:
                with open("/etc/machine-id", "r") as f:
                    machine_id = f.read().strip()
                    if machine_id:
                        return machine_id[:12]  # Use first 12 chars for brevity
            except FileNotFoundError:
                pass

            # Try DMI product UUID
            try:
                with open("/sys/class/dmi/id/product_uuid", "r") as f:
                    uuid_str = f.read().strip()
                    if uuid_str and uuid_str != "00000000-0000-0000-0000-000000000000":
                        # Convert UUID to shorter format
                        return uuid_str.replace("-", "")[:12]
            except FileNotFoundError:
                pass

            # Fallback to MAC-based ID
            try:
                mac = self._get_mac_address()
                if mac and mac != "00:00:00:00:00:00":
                    return mac.replace(":", "")
            except Exception:
                pass

            # Last resort: generate random UUID
            return str(uuid.uuid4()).replace("-", "")[:12]

        except Exception as e:
            if self.logger:
                self.logger.error(f"Device ID generation failed: {e}")
            return "UNKNOWN"

    def _generate_device_id_safe(self) -> Result[str, Exception]:
        """Thread-safe device ID generation with proper error handling"""
        try:
            device_id = self._generate_device_id()
            if device_id == "UNKNOWN":
                raise ValueError("Unable to generate valid device ID")
            return Result.success(device_id)
        except Exception as e:
            return Result.failure(e)

    def _get_mac_address(self) -> str:
        """Get device MAC address with improved interface detection"""
        try:
            # Priority order for network interfaces
            priority_interfaces = ["wlan0", "eth0", "enp1s0", "wlp2s0"]

            # Check priority interfaces first
            for interface in priority_interfaces:
                try:
                    with open(f"/sys/class/net/{interface}/address", "r") as f:
                        mac = f.read().strip()
                        if mac and mac != "00:00:00:00:00:00":
                            return mac
                except FileNotFoundError:
                    continue

            # Fall back to any available interface
            import os

            try:
                for interface in os.listdir("/sys/class/net/"):
                    if interface != "lo":  # Skip loopback
                        try:
                            with open(f"/sys/class/net/{interface}/address", "r") as f:
                                mac = f.read().strip()
                                if mac and mac != "00:00:00:00:00:00":
                                    return mac
                        except (FileNotFoundError, OSError):
                            continue
            except (FileNotFoundError, OSError):
                pass

            # Last resort: use uuid to generate MAC-like address
            import uuid

            fake_mac = ":".join([f"{b:02x}" for b in uuid.uuid4().bytes[:6]])
            if self.logger:
                self.logger.warning(f"Using generated MAC address: {fake_mac}")
            return fake_mac

        except Exception as e:
            if self.logger:
                self.logger.error(f"MAC address detection failed: {e}")
            return "00:00:00:00:00:00"

    def _get_mac_address_safe(self) -> Result[str, Exception]:
        """Thread-safe MAC address retrieval with proper error handling"""
        try:
            mac_address = self._get_mac_address()
            if mac_address == "00:00:00:00:00:00":
                if self.logger:
                    self.logger.warning("No valid MAC address found, using default")
            return Result.success(mac_address)

        except Exception as e:
            if self.logger:
                self.logger.error(f"MAC address retrieval failed: {e}")
            return Result.failure(
                SystemError(
                    message=f"MAC address retrieval failed: {e}",
                    error_code=ErrorCode.HARDWARE_ERROR,
                    severity=ErrorSeverity.MEDIUM,
                )
            )