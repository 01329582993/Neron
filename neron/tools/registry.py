"""Central registry for discovering, inspecting, and safely executing tools."""

import threading
import time
from typing import Any, Dict, List, Optional
from neron.core.events.bus import EventBus, get_default_bus
from neron.core.events.event import EVENT_TOOL_CALLED, EVENT_TOOL_COMPLETED, Event
from neron.security.emergency_stop import EmergencyStopCoordinator, get_emergency_stop
from neron.security.permissions import PermissionRequest
from neron.security.policy import PermissionManager
from neron.tools.base import BaseTool, ToolResult
from neron.utils.audit import AuditLedger
from neron.utils.logger import get_logger

logger = get_logger("tools.registry")


class ToolNotFoundError(Exception):
    pass


class ToolValidationError(Exception):
    pass


class ToolRegistry:
    """Manages available tools, enforces permissions, and records execution audit trails."""

    def __init__(
        self,
        permission_manager: Optional[PermissionManager] = None,
        audit_ledger: Optional[AuditLedger] = None,
        event_bus: Optional[EventBus] = None,
        emergency_stop: Optional[EmergencyStopCoordinator] = None,
    ):
        self._tools: Dict[str, BaseTool] = {}
        self._lock = threading.RLock()
        self.permission_manager = permission_manager or PermissionManager()
        self.audit_ledger = audit_ledger or AuditLedger()
        self.event_bus = event_bus or get_default_bus()
        self.emergency_stop = emergency_stop or get_emergency_stop()

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        with self._lock:
            self._tools[tool.name] = tool
            logger.debug(f"Registered tool '{tool.name}' (Capabilities: {tool.required_capabilities})")

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name."""
        with self._lock:
            if name in self._tools:
                del self._tools[name]
                logger.debug(f"Unregistered tool '{name}'")
                return True
            return False

    def get(self, name: str) -> Optional[BaseTool]:
        """Look up tool by name."""
        with self._lock:
            return self._tools.get(name)

    def has(self, name: str) -> bool:
        """Check if tool is registered."""
        with self._lock:
            return name in self._tools

    def list_tools(self) -> List[BaseTool]:
        """Return list of all registered tools."""
        with self._lock:
            return list(self._tools.values())

    def list_schemas(self) -> List[Dict[str, Any]]:
        """Return tool definitions formatted for LLM function calling."""
        with self._lock:
            return [t.to_llm_tool_definition() for t in self._tools.values()]

    def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        task_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> ToolResult:
        """Execute a tool with full security, emergency stop, and verification enforcement."""
        start_time = time.time()

        # 1. Emergency Stop Assertion
        self.emergency_stop.assert_not_stopped()

        # 2. Tool Lookup
        with self._lock:
            tool = self._tools.get(tool_name)
        if not tool:
            raise ToolNotFoundError(f"Tool '{tool_name}' is not registered.")

        # 3. Argument Validation
        if not tool.validate_arguments(arguments):
            raise ToolValidationError(
                f"Arguments for '{tool_name}' failed schema validation. Expected required fields: "
                f"{tool.parameters_schema.get('required', [])}"
            )

        # 4. Security & Permission Evaluation
        req = PermissionRequest(
            tool_name=tool.name,
            required_capabilities=tool.required_capabilities,
            arguments=arguments,
            task_id=task_id,
            step_id=step_id,
        )
        self.permission_manager.evaluate(req)

        # 5. Check Emergency Stop again immediately before execution
        self.emergency_stop.assert_not_stopped()

        # 6. Publish Tool Called Event
        self.event_bus.publish(Event(
            event_type=EVENT_TOOL_CALLED,
            payload={
                "tool_name": tool.name,
                "arguments": arguments,
                "task_id": task_id,
                "step_id": step_id,
            }
        ))

        # 7. Execute Tool
        try:
            result = tool.execute(arguments)
        except Exception as e:
            logger.error(f"Execution error in tool '{tool.name}': {e}", exc_info=True)
            result = ToolResult(
                success=False,
                output=None,
                error=f"Runtime error executing '{tool.name}': {str(e)}"
            )

        # 8. Post-Execution Verification Hook
        is_verified = tool.verify(arguments, result)
        result.metadata["verified"] = is_verified
        if not is_verified and result.success:
            result.success = False
            result.error = f"Verification failed: Action appeared to succeed, but expected OS state was not verified."
            logger.warning(f"Verification failure for tool '{tool.name}'")

        duration_ms = (time.time() - start_time) * 1000
        result.metadata["duration_ms"] = round(duration_ms, 2)

        # 9. Record Audit Log
        self.audit_ledger.record_event(
            tool_name=tool.name,
            capabilities=tool.required_capabilities,
            decision="EXECUTED",
            success=result.success,
            task_id=task_id,
            step_id=step_id,
            arguments=arguments,
            result_summary=str(result.output)[:200] if result.output else (result.error or ""),
            duration_ms=duration_ms,
        )

        # 10. Publish Tool Completed Event
        self.event_bus.publish(Event(
            event_type=EVENT_TOOL_COMPLETED,
            payload={
                "tool_name": tool.name,
                "success": result.success,
                "duration_ms": duration_ms,
                "task_id": task_id,
                "step_id": step_id,
            }
        ))

        return result
