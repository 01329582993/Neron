"""Event models and standard event types for Neron's decoupled event bus."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Dict, Optional
import uuid


class EventPriority(Enum):
    LOW = auto()
    NORMAL = auto()
    HIGH = auto()
    CRITICAL = auto()


@dataclass
class Event:
    """Base event representation."""
    event_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "core"
    priority: EventPriority = EventPriority.NORMAL


# Standard Event Types
EVENT_EMERGENCY_STOP = "emergency.stop"
EVENT_TASK_CREATED = "task.created"
EVENT_TASK_STATE_CHANGED = "task.state_changed"
EVENT_TASK_COMPLETED = "task.completed"
EVENT_TASK_FAILED = "task.failed"
EVENT_TOOL_CALLED = "tool.called"
EVENT_TOOL_COMPLETED = "tool.completed"
EVENT_SECURITY_PROMPT = "security.prompt"
EVENT_SECURITY_DECISION = "security.decision"
EVENT_SYSTEM_ALERT = "system.alert"
EVENT_VOICE_WAKE = "voice.wake"


@dataclass
class EmergencyStopEvent(Event):
    def __init__(self, reason: str = "User requested emergency stop", source: str = "user"):
        super().__init__(
            event_type=EVENT_EMERGENCY_STOP,
            payload={"reason": reason},
            source=source,
            priority=EventPriority.CRITICAL,
        )


@dataclass
class TaskStateChangedEvent(Event):
    def __init__(self, task_id: str, old_state: str, new_state: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            event_type=EVENT_TASK_STATE_CHANGED,
            payload={
                "task_id": task_id,
                "old_state": old_state,
                "new_state": new_state,
                "details": details or {},
            },
            priority=EventPriority.NORMAL,
        )
