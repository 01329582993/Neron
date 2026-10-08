"""System management and desktop telemetry tools."""

import time
from typing import Any, Dict, List, Optional
from neron.os.base import OSController, get_os_controller
from neron.security.permissions import Capability
from neron.tools.base import BaseTool, ToolResult
from neron.utils.logger import get_logger

logger = get_logger("tools.system")


class SystemTelemetryTool(BaseTool):
    """Retrieve real-time hardware telemetry and system resource metrics."""

    def __init__(self, os_controller: Optional[OSController] = None):
        self.os_controller = os_controller or get_os_controller()

    @property
    def name(self) -> str:
        return "system.telemetry"

    @property
    def description(self) -> str:
        return "Query live CPU load, RAM usage, storage availability, and battery status."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.SYSTEM_INSPECT]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        try:
            t = self.os_controller.get_telemetry()
            return ToolResult(
                success=True,
                output={
                    "os": f"{t.os_name} ({t.os_version})",
                    "cpu_percent": t.cpu_percent,
                    "cpu_cores": t.cpu_count,
                    "memory_total_gb": t.memory_total_gb,
                    "memory_used_gb": t.memory_used_gb,
                    "memory_percent": t.memory_percent,
                    "disk_free_gb": t.disk_free_gb,
                    "disk_total_gb": t.disk_total_gb,
                    "disk_percent": t.disk_percent,
                    "battery_percent": t.battery_percent,
                    "is_charging": t.is_charging,
                    "uptime_hours": round(t.uptime_seconds / 3600, 2),
                }
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class SystemLaunchAppTool(BaseTool):
    """Launch an application with post-launch process verification."""

    def __init__(self, os_controller: Optional[OSController] = None):
        self.os_controller = os_controller or get_os_controller()

    @property
    def name(self) -> str:
        return "system.open_app"

    @property
    def description(self) -> str:
        return "Launch a desktop application by name or path."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Application name or executable name (e.g. 'notepad', 'chrome')."},
                "args": {"type": "array", "items": {"type": "string"}, "description": "Optional CLI arguments."}
            },
            "required": ["app_name"]
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.APPLICATION_CONTROL]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        app_name = arguments.get("app_name", "").strip()
        args = arguments.get("args")
        success = self.os_controller.open_application(app_name, args)
        return ToolResult(
            success=success,
            output=f"Application '{app_name}' launch command dispatched." if success else None,
            error=f"Failed to launch application '{app_name}'" if not success else None
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> bool:
        """Verify that a matching process has started."""
        if not result.success:
            return False
        # Small grace period for process to spawn
        time.sleep(0.5)
        app_name = arguments.get("app_name", "").strip()
        matches = self.os_controller.find_process(app_name)
        return len(matches) > 0


class SystemCloseAppTool(BaseTool):
    """Close an application with post-close process verification."""

    def __init__(self, os_controller: Optional[OSController] = None):
        self.os_controller = os_controller or get_os_controller()

    @property
    def name(self) -> str:
        return "system.close_app"

    @property
    def description(self) -> str:
        return "Close a running application by process name."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Application name to close."}
            },
            "required": ["app_name"]
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.APPLICATION_CONTROL]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        app_name = arguments.get("app_name", "").strip()
        success = self.os_controller.close_application(app_name)
        return ToolResult(
            success=success,
            output=f"Closed application '{app_name}'." if success else None,
            error=f"Could not find or close application '{app_name}'" if not success else None
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> bool:
        """Verify process is no longer active."""
        if not result.success:
            return False
        time.sleep(0.3)
        app_name = arguments.get("app_name", "").strip()
        matches = self.os_controller.find_process(app_name)
        return len(matches) == 0


class SystemVolumeTool(BaseTool):
    """Query or set system audio volume."""

    def __init__(self, os_controller: Optional[OSController] = None):
        self.os_controller = os_controller or get_os_controller()

    @property
    def name(self) -> str:
        return "system.volume"

    @property
    def description(self) -> str:
        return "Query or set the master system volume level (0-100)."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "level": {"type": "integer", "description": "Target volume level (0-100). If omitted, queries current volume."}
            },
            "required": []
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.SYSTEM_ADMIN]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        level = arguments.get("level")
        if level is not None:
            success = self.os_controller.set_volume(int(level))
            return ToolResult(
                success=success,
                output=f"Set system volume to {level}%" if success else None,
                error="Failed to set system volume." if not success else None
            )
        else:
            current = self.os_controller.get_volume()
            if current is not None:
                return ToolResult(success=True, output={"volume": current})
            return ToolResult(success=True, output={"volume": "Query unsupported on this audio driver."})
