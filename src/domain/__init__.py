"""
Domain Layer - Core business logic and rules
This layer contains the core domain models, events, and business rules.
"""

from .configuration import ProvisioningConfig, load_config
from .configuration_factory import ConfigurationFactory, IConfigurationLoader
from .errors import (
    BLEError,
    ErrorCode,
    ErrorSeverity,
    NetworkError,
    ProvisioningError,
    SecurityError,
    SystemError,
    ValidationError,
)
from .events import Event, EventBus, EventType, get_event_bus
from .specifications import (
    DevicePinSpecification,
    ISpecification,
    NetworkCredentialsSpecification,
    SpecificationBasedValidationService,
    SpecificationFactory,
    StrongPasswordSpecification,
    ValidSSIDSpecification,
)
from .state import ProvisioningEvent, ProvisioningStateMachine, StateTransition
from .validation import ValidationService

__all__ = [
    # Configuration
    "ProvisioningConfig",
    "load_config",
    "ConfigurationFactory",
    "IConfigurationLoader",
    # Errors
    "ErrorCode",
    "ErrorSeverity",
    "ProvisioningError",
    "NetworkError",
    "BLEError",
    "SecurityError",
    "SystemError",
    "ValidationError",
    # Events
    "EventBus",
    "EventType",
    "Event",
    "get_event_bus",
    # State
    "ProvisioningStateMachine",
    "ProvisioningEvent",
    "StateTransition",
    # Validation
    "ValidationService",
    # Specifications
    "ISpecification",
    "ValidSSIDSpecification",
    "StrongPasswordSpecification",
    "NetworkCredentialsSpecification",
    "DevicePinSpecification",
    "SpecificationFactory",
    "SpecificationBasedValidationService",
]
