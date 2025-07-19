"""
Legacy device module - now redirects to refactored modules
This file maintains backward compatibility while the new modules provide enhanced functionality
"""

# Import the new refactored classes
from .device.detector import DeviceDetector
from .device.info_provider import DeviceInfoProvider

# Re-export everything for backward compatibility
__all__ = ["DeviceDetector", "DeviceInfoProvider"]

# Note: This module has been refactored into:
# - src/infrastructure/device/detector.py - Hardware detection logic  
# - src/infrastructure/device/info_provider.py - Device information provision
# This maintains the same public interface while improving code organization and reducing file size.
