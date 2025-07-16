"""
GPIO service implementation - now redirects to dynamic GPIO service
"""

# Re-export the dynamic GPIO service for backward compatibility
from .dynamic_gpio import DynamicGPIOService

# Backward compatibility aliases
RockPi4BPlusGPIOService = DynamicGPIOService
GPIOService = DynamicGPIOService

# Export for imports
__all__ = ["DynamicGPIOService", "RockPi4BPlusGPIOService", "GPIOService"]
