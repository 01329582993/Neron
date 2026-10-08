"""Terminal and command execution tool."""

from typing import Any, Dict, List, Optional
from neron.os.base import OSController, get_os_controller
from neron.security.permissions import Capability
from neron.tools.base import BaseTool, ToolResult
from neron.utils.logger import get_logger

logger = get_logger("tools.terminal")


class TerminalExecuteTool(BaseTool):
    """Executes a shell/terminal command through the OS abstraction layer."""

    def __init__(self, os_controller: Optional[OSController] = None):
        self.os_controller = os_controller or get_os_controller()

    @property
    def name(self) -> str:
        return "terminal.execute"

    @property
    def description(self) -> str:
        return "Execute a terminal/shell command with timeout and environment isolation."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command string to execute."},
                "cwd": {"type": "string", "description": "Optional working directory."},
                "timeout": {"type": "integer", "description": "Execution timeout in seconds (default 30)."}
            },
            "required": ["command"]
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.TERMINAL_EXECUTE]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        command = arguments.get("command", "").strip()
        cwd = arguments.get("cwd")
        timeout = arguments.get("timeout", 30)

        if not command:
            return ToolResult(success=False, output=None, error="Empty command string provided.")

        res = self.os_controller.execute_terminal_command(
            command=command,
            cwd=cwd,
            timeout=timeout
        )

        success = res["exit_code"] == 0
        return ToolResult(
            success=success,
            output={
                "exit_code": res["exit_code"],
                "stdout": res["stdout"],
                "stderr": res["stderr"],
                "timed_out": res.get("timed_out", False),
            },
            error=res["stderr"] if not success and not res["stdout"] else None,
            metadata={"duration_ms": res.get("duration_ms", 0.0)}
        )
