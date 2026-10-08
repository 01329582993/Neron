"""Neron security and permission subsystem."""

from neron.security.emergency_stop import (
    EmergencyStopCoordinator,
    EmergencyStopTriggered,
    get_emergency_stop,
)
from neron.security.permissions import (
    Capability,
    PermissionDecision,
    PermissionRequest,
    SecurityMode,
)
from neron.security.policy import (
    PermissionDeniedError,
    PermissionManager,
    PromptHandler,
)

__all__ = [
    "Capability",
    "SecurityMode",
    "PermissionDecision",
    "PermissionRequest",
    "PermissionManager",
    "PermissionDeniedError",
    "PromptHandler",
    "EmergencyStopCoordinator",
    "EmergencyStopTriggered",
    "get_emergency_stop",
]
