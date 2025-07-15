"""
Event bus for decoupled communication between layers
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4


class EventType(Enum):
    """System event types"""

    # Provisioning events
    PROVISIONING_STARTED = "provisioning_started"
    PROVISIONING_COMPLETED = "provisioning_completed"
    PROVISIONING_FAILED = "provisioning_failed"

    # Network events
    NETWORK_SCAN_STARTED = "network_scan_started"
    NETWORK_SCAN_COMPLETED = "network_scan_completed"
    NETWORK_CONNECTION_STARTED = "network_connection_started"
    NETWORK_CONNECTION_SUCCESS = "network_connection_success"
    NETWORK_CONNECTION_FAILED = "network_connection_failed"
    NETWORK_DISCONNECTED = "network_disconnected"

    # BLE events
    BLE_ADVERTISING_STARTED = "ble_advertising_started"
    BLE_ADVERTISING_STOPPED = "ble_advertising_stopped"
    BLE_CLIENT_CONNECTED = "ble_client_connected"
    BLE_CLIENT_DISCONNECTED = "ble_client_disconnected"
    BLE_CREDENTIALS_RECEIVED = "ble_credentials_received"

    # Display events
    DISPLAY_QR_SHOWN = "display_qr_shown"
    DISPLAY_STATUS_UPDATED = "display_status_updated"
    DISPLAY_ERROR = "display_error"

    # Security events
    SECURITY_VIOLATION = "security_violation"
    SESSION_CREATED = "session_created"
    SESSION_EXPIRED = "session_expired"
    AUTHENTICATION_FAILED = "authentication_failed"

    # System events
    SYSTEM_HEALTH_CHECK = "system_health_check"
    SYSTEM_ERROR = "system_error"
    FACTORY_RESET_TRIGGERED = "factory_reset_triggered"
    OWNER_SETUP_STARTED = "owner_setup_started"


@dataclass
class Event:
    """Event data structure"""

    type: EventType
    data: Any
    timestamp: datetime
    source: str
    event_id: str


class EventBus:
    """Event bus for publish-subscribe communication"""

    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable[[Event], None]]] = {}
        self._async_subscribers: Dict[EventType, List[Callable[[Event], Any]]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000

    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> str:
        """Subscribe to synchronous events"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        self._subscribers[event_type].append(handler)
        return str(uuid4())

    def subscribe_async(
        self, event_type: EventType, handler: Callable[[Event], Any]
    ) -> str:
        """Subscribe to asynchronous events"""
        if event_type not in self._async_subscribers:
            self._async_subscribers[event_type] = []

        self._async_subscribers[event_type].append(handler)
        return str(uuid4())

    def publish(
        self, event_type: EventType, data: Any, source: str = "unknown"
    ) -> None:
        """Publish an event synchronously"""
        event = Event(
            type=event_type,
            data=data,
            timestamp=datetime.now(),
            source=source,
            event_id=str(uuid4()),
        )

        self._add_to_history(event)

        # Notify synchronous subscribers
        if event_type in self._subscribers:
            for handler in self._subscribers[event_type]:
                try:
                    handler(event)
                except Exception as e:
                    print(f"Error in event handler: {e}")

    async def publish_async(
        self, event_type: EventType, data: Any, source: str = "unknown"
    ) -> None:
        """Publish an event asynchronously"""
        event = Event(
            type=event_type,
            data=data,
            timestamp=datetime.now(),
            source=source,
            event_id=str(uuid4()),
        )

        self._add_to_history(event)

        # Notify synchronous subscribers first
        if event_type in self._subscribers:
            for handler in self._subscribers[event_type]:
                try:
                    handler(event)
                except Exception as e:
                    print(f"Error in sync event handler: {e}")

        # Notify async subscribers
        if event_type in self._async_subscribers:
            tasks = []
            for handler in self._async_subscribers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        tasks.append(handler(event))
                    else:
                        handler(event)
                except Exception as e:
                    print(f"Error in async event handler: {e}")

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    def _add_to_history(self, event: Event) -> None:
        """Add event to history"""
        self._event_history.append(event)

        # Trim history if needed
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history :]

    def get_event_history(
        self, event_type: Optional[EventType] = None, limit: int = 100
    ) -> List[Event]:
        """Get event history"""
        events = self._event_history

        if event_type:
            events = [e for e in events if e.type == event_type]

        return events[-limit:]

    def clear_history(self) -> None:
        """Clear event history"""
        self._event_history.clear()


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset the global event bus (useful for testing)"""
    global _event_bus
    _event_bus = None
