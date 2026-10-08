"""Permission definitions, capabilities, and security profiles for Neron."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SecurityMode(Enum):
    SAFE = "SAFE"
    STANDARD = "STANDARD"
    POWER_USER = "POWER_USER"
    CUSTOM = "CUSTOM"


class PermissionDecision(Enum):
    GRANTED = "GRANTED"
    DENIED = "DENIED"
    PROMPTED_APPROVED = "PROMPTED_APPROVED"
    PROMPTED_DENIED = "PROMPTED_DENIED"


class Capability:
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    FILESYSTEM_DELETE = "filesystem.delete"
    TERMINAL_EXECUTE = "terminal.execute"
    COMPUTER_SCREEN = "computer.screen"
    COMPUTER_MOUSE = "computer.mouse"
    COMPUTER_KEYBOARD = "computer.keyboard"
    APPLICATION_CONTROL = "application.control"
    SYSTEM_INSPECT = "system.inspect"
    SYSTEM_ADMIN = "system.admin"
    NETWORK_ACCESS = "network.access"
    SELF_MODIFY = "self.modify"
    PLUGIN_INSTALL = "plugin.install"

    ALL = {
        FILESYSTEM_READ,
        FILESYSTEM_WRITE,
        FILESYSTEM_DELETE,
        TERMINAL_EXECUTE,
        COMPUTER_SCREEN,
        COMPUTER_MOUSE,
        COMPUTER_KEYBOARD,
        APPLICATION_CONTROL,
        SYSTEM_INSPECT,
        SYSTEM_ADMIN,
        NETWORK_ACCESS,
        SELF_MODIFY,
        PLUGIN_INSTALL,
    }


@dataclass
class PermissionRequest:
    tool_name: str
    required_capabilities: List[str]
    arguments: Dict[str, Any] = field(default_factory=dict)
    task_id: Optional[str] = None
    step_id: Optional[str] = None
    reason: Optional[str] = None
