"""
Bluetooth module for BLE 5.0 support on ROCK Pi 4B+
Refactored into smaller, focused modules for better maintainability
"""

from .service import BluetoothService

__all__ = ["BluetoothService"]