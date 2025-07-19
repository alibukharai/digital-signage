"""
Bluetooth service implementation - refactored into smaller modules
This file provides backwards compatibility by re-exporting from the bluetooth module
"""

# Import from the refactored module
from .bluetooth.service import BluetoothService

# Re-export for backwards compatibility
__all__ = ["BluetoothService"]
