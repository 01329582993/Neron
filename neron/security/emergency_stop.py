"""Global emergency stop coordinator and interrupt handler."""

import threading
from typing import Callable, List, Optional
from neron.core.events.bus import EventBus, get_default_bus
from neron.core.events.event import EmergencyStopEvent
from neron.utils.logger import get_logger

logger = get_logger("security.emergency_stop")


class EmergencyStopTriggered(Exception):
    """Exception raised when an operation is aborted by emergency stop."""
    pass


class EmergencyStopCoordinator:
    """Coordinates global interruption across running tools, planners, and sub-processes."""

    def __init__(self, event_bus: Optional[EventBus] = None):
        self._stopped = threading.Event()
        self._event_bus = event_bus or get_default_bus()
        self._hooks: List[Callable[[], None]] = []
        self._lock = threading.Lock()

    def is_stopped(self) -> bool:
        """Check if emergency stop is currently active."""
        return self._stopped.is_set()

    def register_cleanup_hook(self, hook: Callable[[], None]) -> None:
        """Register a callback invoked when emergency stop fires (e.g. process termination)."""
        with self._lock:
            if hook not in self._hooks:
                self._hooks.append(hook)

    def trigger(self, reason: str = "User triggered emergency stop", source: str = "user") -> None:
        """Trigger global emergency stop."""
        if not self._stopped.is_set():
            self._stopped.set()
            logger.critical(f"🛑 EMERGENCY STOP TRIGGERED: {reason} (Source: {source})")
            
            # Publish critical event
            event = EmergencyStopEvent(reason=reason, source=source)
            self._event_bus.publish(event)

            # Execute all cleanup hooks
            with self._lock:
                hooks = list(self._hooks)
            for hook in hooks:
                try:
                    hook()
                except Exception as e:
                    logger.error(f"Error in emergency cleanup hook: {e}")

    def reset(self) -> None:
        """Reset the emergency stop state to resume normal operations."""
        if self._stopped.is_set():
            self._stopped.clear()
            logger.info("Emergency stop flag reset. System returned to normal operations.")

    def assert_not_stopped(self) -> None:
        """Helper to raise EmergencyStopTriggered if stop flag is set."""
        if self._stopped.is_set():
            raise EmergencyStopTriggered("Operation aborted: Emergency stop is active.")


# Global default coordinator instance
_default_stop_coordinator: Optional[EmergencyStopCoordinator] = None


def get_emergency_stop() -> EmergencyStopCoordinator:
    global _default_stop_coordinator
    if _default_stop_coordinator is None:
        _default_stop_coordinator = EmergencyStopCoordinator()
    return _default_stop_coordinator
