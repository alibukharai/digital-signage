"""
Security service implementation - refactored into smaller modules
This file provides backwards compatibility by re-exporting from the security module
"""

# Import from the refactored module
from .security.service import SecurityService

# Re-export for backwards compatibility
__all__ = ["SecurityService"]
