"""Neron events subsystem."""

from neron.core.events.bus import EventBus, get_default_bus
from neron.core.events.event import (
    EVENT_EMERGENCY_STOP,
    EVENT_SECURITY_DECISION,
    EVENT_SECURITY_PROMPT,
    EVENT_SYSTEM_ALERT,
    EVENT_TASK_COMPLETED,
    EVENT_TASK_CREATED,
    EVENT_TASK_FAILED,
    EVENT_TASK_STATE_CHANGED,
    EVENT_TOOL_CALLED,
    EVENT_TOOL_COMPLETED,
    EVENT_VOICE_WAKE,
    EmergencyStopEvent,
    Event,
    EventPriority,
    TaskStateChangedEvent,
)

__all__ = [
    "EventBus",
    "get_default_bus",
    "Event",
    "EventPriority",
    "EmergencyStopEvent",
    "TaskStateChangedEvent",
    "EVENT_EMERGENCY_STOP",
    "EVENT_TASK_CREATED",
    "EVENT_TASK_STATE_CHANGED",
    "EVENT_TASK_COMPLETED",
    "EVENT_TASK_FAILED",
    "EVENT_TOOL_CALLED",
    "EVENT_TOOL_COMPLETED",
    "EVENT_SECURITY_PROMPT",
    "EVENT_SECURITY_DECISION",
    "EVENT_SYSTEM_ALERT",
    "EVENT_VOICE_WAKE",
]
