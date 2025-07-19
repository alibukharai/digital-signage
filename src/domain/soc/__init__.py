"""
SOC (System-on-Chip) specifications module
Refactored for better maintainability and organization
"""

from .base_types import SOCFamily, ArchitectureType, PerformanceProfile, ConnectivityProfile, IOProfile, PowerProfile
from .specifications import SOCSpecification, RockchipRK3399, RockchipOP1
from .manager import SOCManager

# Create global instance
soc_manager = SOCManager()

__all__ = [
    "SOCFamily",
    "ArchitectureType", 
    "PerformanceProfile",
    "ConnectivityProfile",
    "IOProfile",
    "PowerProfile",
    "SOCSpecification",
    "RockchipRK3399",
    "RockchipOP1",
    "SOCManager",
    "soc_manager"
]