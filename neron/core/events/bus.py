"""Thread-safe, decoupled EventBus for Neron core operations."""

import threading
from collections import deque
from typing import Callable, Deque, Dict, List, Optional
from neron.core.events.event import Event, EventPriority
from neron.utils.logger import get_logger

logger = get_logger("event_bus")

EventHandler = Callable[[Event], None]


class EventBus:
    """Central decoupled pub/sub message router."""

    def __init__(self, history_size: int = 100):
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._wildcard_handlers: List[EventHandler] = []
        self._lock = threading.RLock()
        self._history: Deque[Event] = deque(maxlen=history_size)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for a specific event type or wildcard '*'."""
        with self._lock:
            if event_type == "*":
                if handler not in self._wildcard_handlers:
                    self._wildcard_handlers.append(handler)
            else:
                if event_type not in self._handlers:
                    self._handlers[event_type] = []
                if handler not in self._handlers[event_type]:
                    self._handlers[event_type].append(handler)
        logger.debug(f"Subscribed handler {handler.__name__ if hasattr(handler, '__name__') else handler} to '{event_type}'")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> bool:
        """Unregister a previously registered handler."""
        with self._lock:
            if event_type == "*":
                if handler in self._wildcard_handlers:
                    self._wildcard_handlers.remove(handler)
                    return True
            elif event_type in self._handlers:
                if handler in self._handlers[event_type]:
                    self._handlers[event_type].remove(handler)
                    return True
        return False

    def publish(self, event: Event) -> None:
        """Publish an event to all registered matching handlers synchronously."""
        with self._lock:
            self._history.append(event)
            # Make copies of handler lists to safely iterate outside lock modifications
            specific_handlers = list(self._handlers.get(event.event_type, []))
            wildcard_handlers = list(self._wildcard_handlers)

        # Notify specific handlers first, then wildcards
        for handler in specific_handlers:
            self._invoke_handler(handler, event)

        for handler in wildcard_handlers:
            self._invoke_handler(handler, event)

    def _invoke_handler(self, handler: EventHandler, event: Event) -> None:
        """Execute a handler with exception isolation."""
        try:
            handler(event)
        except Exception as e:
            logger.error(
                f"Error in event handler '{getattr(handler, '__name__', str(handler))}' "
                f"for event '{event.event_type}': {e}",
                exc_info=True
            )

    def get_history(self) -> List[Event]:
        """Return a snapshot of recently published events."""
        with self._lock:
            return list(self._history)

    def clear(self) -> None:
        """Clear all handlers and event history."""
        with self._lock:
            self._handlers.clear()
            self._wildcard_handlers.clear()
            self._history.clear()


# Global shared singleton bus instance for standard use
_default_bus: Optional[EventBus] = None


def get_default_bus() -> EventBus:
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus
