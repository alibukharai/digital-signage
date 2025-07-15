"""
State machine for managing provisioning workflow
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional

from ..interfaces import DeviceState, ILogger, IStateMachine
from .events import EventBus, EventType


class ProvisioningEvent(Enum):
    """Events that can trigger state transitions"""

    START_PROVISIONING = "start_provisioning"
    START_OWNER_SETUP = "start_owner_setup"
    OWNER_REGISTERED = "owner_registered"
    NETWORK_SCAN_COMPLETE = "network_scan_complete"
    CREDENTIALS_RECEIVED = "credentials_received"
    NETWORK_CONNECTED = "network_connected"
    CONNECTION_FAILED = "connection_failed"
    TIMEOUT = "timeout"
    ERROR_OCCURRED = "error_occurred"
    RESET_TRIGGERED = "reset_triggered"
    PROVISIONING_COMPLETE = "provisioning_complete"


@dataclass
class StateTransition:
    """Represents a state transition"""

    from_state: DeviceState
    event: ProvisioningEvent
    to_state: DeviceState
    condition: Optional[Callable[[Any], bool]] = None
    action: Optional[Callable[[Any], None]] = None


class ProvisioningStateMachine(IStateMachine):
    """State machine for managing provisioning workflow"""

    def __init__(self, event_bus: EventBus, logger: Optional[ILogger] = None):
        self.current_state = DeviceState.INITIALIZING
        self.event_bus = event_bus
        self.logger = logger
        self.state_history = []
        self.context: Dict[str, Any] = {}

        # Define state transitions
        self.transitions = [
            # From INITIALIZING
            StateTransition(
                DeviceState.INITIALIZING,
                ProvisioningEvent.START_OWNER_SETUP,
                DeviceState.READY,
            ),
            StateTransition(
                DeviceState.INITIALIZING,
                ProvisioningEvent.START_PROVISIONING,
                DeviceState.PROVISIONING,
            ),
            # From READY
            StateTransition(
                DeviceState.READY,
                ProvisioningEvent.START_PROVISIONING,
                DeviceState.PROVISIONING,
            ),
            StateTransition(
                DeviceState.READY,
                ProvisioningEvent.OWNER_REGISTERED,
                DeviceState.PROVISIONING,
            ),
            # From PROVISIONING
            StateTransition(
                DeviceState.PROVISIONING,
                ProvisioningEvent.CREDENTIALS_RECEIVED,
                DeviceState.PROVISIONING,  # Stay in provisioning while connecting
            ),
            StateTransition(
                DeviceState.PROVISIONING,
                ProvisioningEvent.NETWORK_CONNECTED,
                DeviceState.CONNECTED,
            ),
            StateTransition(
                DeviceState.PROVISIONING,
                ProvisioningEvent.CONNECTION_FAILED,
                DeviceState.PROVISIONING,  # Retry in provisioning
            ),
            StateTransition(
                DeviceState.PROVISIONING, ProvisioningEvent.TIMEOUT, DeviceState.ERROR
            ),
            # From CONNECTED
            StateTransition(
                DeviceState.CONNECTED,
                ProvisioningEvent.PROVISIONING_COMPLETE,
                DeviceState.READY,
            ),
            # Error transitions (from any state)
            StateTransition(
                DeviceState.INITIALIZING,
                ProvisioningEvent.ERROR_OCCURRED,
                DeviceState.ERROR,
            ),
            StateTransition(
                DeviceState.READY, ProvisioningEvent.ERROR_OCCURRED, DeviceState.ERROR
            ),
            StateTransition(
                DeviceState.PROVISIONING,
                ProvisioningEvent.ERROR_OCCURRED,
                DeviceState.ERROR,
            ),
            StateTransition(
                DeviceState.CONNECTED,
                ProvisioningEvent.ERROR_OCCURRED,
                DeviceState.ERROR,
            ),
            # Factory reset transitions (from any state)
            StateTransition(
                DeviceState.INITIALIZING,
                ProvisioningEvent.RESET_TRIGGERED,
                DeviceState.FACTORY_RESET,
            ),
            StateTransition(
                DeviceState.READY,
                ProvisioningEvent.RESET_TRIGGERED,
                DeviceState.FACTORY_RESET,
            ),
            StateTransition(
                DeviceState.PROVISIONING,
                ProvisioningEvent.RESET_TRIGGERED,
                DeviceState.FACTORY_RESET,
            ),
            StateTransition(
                DeviceState.CONNECTED,
                ProvisioningEvent.RESET_TRIGGERED,
                DeviceState.FACTORY_RESET,
            ),
            StateTransition(
                DeviceState.ERROR,
                ProvisioningEvent.RESET_TRIGGERED,
                DeviceState.FACTORY_RESET,
            ),
        ]

        # Create transition lookup table
        self.transition_map: Dict[tuple, StateTransition] = {}
        for transition in self.transitions:
            key = (transition.from_state, transition.event)
            self.transition_map[key] = transition

    def process_event(self, event: ProvisioningEvent, data: Any = None) -> bool:
        """Process an event and potentially transition state"""
        key = (self.current_state, event)

        if key not in self.transition_map:
            if self.logger:
                self.logger.warning(
                    f"No transition defined for event {event.value} in state {self.current_state.value}"
                )
            return False

        transition = self.transition_map[key]

        # Check condition if defined
        if transition.condition and not transition.condition(data):
            if self.logger:
                self.logger.debug(
                    f"Transition condition failed for {event.value} in state {self.current_state.value}"
                )
            return False

        # Record state change
        old_state = self.current_state
        self.current_state = transition.to_state

        # Add to history
        self.state_history.append(
            {
                "from_state": old_state,
                "to_state": self.current_state,
                "event": event,
                "timestamp": datetime.now(),
                "data": data,
            }
        )

        # Execute action if defined
        if transition.action:
            try:
                transition.action(data)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error executing transition action: {e}")

        # Publish state change event
        self.event_bus.publish(
            EventType.PROVISIONING_STARTED
            if self.current_state == DeviceState.PROVISIONING
            else EventType.PROVISIONING_COMPLETED
            if self.current_state == DeviceState.CONNECTED
            else EventType.PROVISIONING_FAILED
            if self.current_state == DeviceState.ERROR
            else EventType.SYSTEM_ERROR,
            {
                "old_state": old_state.value,
                "new_state": self.current_state.value,
                "event": event.value,
                "data": data,
            },
            "state_machine",
        )

        if self.logger:
            self.logger.info(
                f"State transition: {old_state.value} -> {self.current_state.value} (event: {event.value})"
            )

        return True

    def get_current_state(self) -> DeviceState:
        """Get current state"""
        return self.current_state

    def can_process_event(self, event: ProvisioningEvent) -> bool:
        """Check if an event can be processed in current state"""
        key = (self.current_state, event)
        return key in self.transition_map

    def get_valid_events(self) -> list[ProvisioningEvent]:
        """Get list of valid events for current state"""
        valid_events = []
        for state, event in self.transition_map.keys():
            if state == self.current_state:
                valid_events.append(event)
        return valid_events

    def get_state_history(self, limit: int = 10) -> list[Dict[str, Any]]:
        """Get recent state history"""
        return self.state_history[-limit:] if limit > 0 else self.state_history

    def reset(self) -> None:
        """Reset state machine to initial state"""
        old_state = self.current_state
        self.current_state = DeviceState.INITIALIZING
        self.context.clear()

        if self.logger:
            self.logger.info(
                f"State machine reset: {old_state.value} -> {self.current_state.value}"
            )

    def set_context(self, key: str, value: Any) -> None:
        """Set context data"""
        self.context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get context data"""
        return self.context.get(key, default)

    def clear_context(self) -> None:
        """Clear all context data"""
        self.context.clear()
