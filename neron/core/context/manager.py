"""Context engine for aggregating environmental, system, and conversational state."""

from pathlib import Path
from typing import Any, Dict, List, Optional
from neron.os.base import OSController, get_os_controller
from neron.utils.logger import get_logger

logger = get_logger("core.context")


class ContextManager:
    """Maintains and gathers conversational, window, project, and desktop context."""

    def __init__(self, os_controller: Optional[OSController] = None):
        self.os_controller = os_controller or get_os_controller()
        self.conversation_history: List[Dict[str, str]] = []
        self.user_preferences: Dict[str, Any] = {}
        self.active_project_path: Optional[Path] = Path.cwd()

    def add_message(self, role: str, content: str) -> None:
        """Add a turn to short-term conversation context."""
        self.conversation_history.append({"role": role, "content": content})
        if len(self.conversation_history) > 30:
            self.conversation_history.pop(0)

    def set_active_project(self, path: Path) -> None:
        """Set the active workspace/project directory."""
        self.active_project_path = Path(path).resolve()

    def get_snapshot(self) -> Dict[str, Any]:
        """Aggregate current environmental context for the planner."""
        active_window = None
        try:
            win = self.os_controller.get_active_window()
            if win:
                active_window = {"title": win.title, "process": win.process_name}
        except Exception:
            pass

        telemetry = None
        try:
            t = self.os_controller.get_telemetry()
            telemetry = {
                "cpu_percent": t.cpu_percent,
                "memory_percent": t.memory_percent,
                "disk_free_gb": t.disk_free_gb,
            }
        except Exception:
            pass

        return {
            "cwd": str(Path.cwd()),
            "active_project": str(self.active_project_path) if self.active_project_path else None,
            "active_window": active_window,
            "platform": self.os_controller.get_platform_name(),
            "telemetry": telemetry,
            "preferences": dict(self.user_preferences),
            "history_turns": len(self.conversation_history),
        }
