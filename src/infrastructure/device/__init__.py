"""
Device management module for hardware detection and information provision
"""

from .detector import DeviceDetector
from .info_provider import DeviceInfoProvider

__all__ = ["DeviceDetector", "DeviceInfoProvider"]