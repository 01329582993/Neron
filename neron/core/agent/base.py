"""Neron core agent coordinator."""

from typing import Any, Dict, Optional
from neron.config.manager import ConfigManager
from neron.core.context.manager import ContextManager
from neron.core.events.bus import EventBus, get_default_bus
from neron.core.executor.base import ExecutionEngine
from neron.core.planner.base import BasePlanner, HeuristicPlanner
from neron.core.state.models import TaskPlan
from neron.os.base import OSController, get_os_controller
from neron.security.emergency_stop import EmergencyStopCoordinator, get_emergency_stop
from neron.security.permissions import SecurityMode
from neron.security.policy import PermissionManager
from neron.tools import create_default_registry
from neron.tools.registry import ToolRegistry
from neron.utils.logger import get_logger

logger = get_logger("core.agent")


class NeronAgent:
    """Central agent orchestrating perception, planning, tool dispatch, and execution."""

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        os_controller: Optional[OSController] = None,
        permission_manager: Optional[PermissionManager] = None,
        tool_registry: Optional[ToolRegistry] = None,
        planner: Optional[BasePlanner] = None,
        event_bus: Optional[EventBus] = None,
        emergency_stop: Optional[EmergencyStopCoordinator] = None,
    ):
        self.config_manager = config_manager or ConfigManager()
        self.os_controller = os_controller or get_os_controller()
        self.event_bus = event_bus or get_default_bus()
        self.emergency_stop = emergency_stop or get_emergency_stop()

        # Initialize permission engine with configured security mode
        configured_mode = SecurityMode(self.config_manager.config.security.profile)
        self.permission_manager = permission_manager or PermissionManager(
            mode=configured_mode,
            event_bus=self.event_bus,
            custom_policies=self.config_manager.config.security.custom_policies,
        )

        # Initialize tools
        self.tool_registry = tool_registry or create_default_registry(
            permission_manager=self.permission_manager,
            os_controller=self.os_controller,
        )

        # Initialize context and planner
        self.context_manager = ContextManager(os_controller=self.os_controller)
        self.planner = planner or HeuristicPlanner()

        # Initialize executor
        self.executor = ExecutionEngine(
            tool_registry=self.tool_registry,
            event_bus=self.event_bus,
            emergency_stop=self.emergency_stop,
        )

    def run_goal(self, goal: str) -> TaskPlan:
        """High-level entrypoint: Takes user natural language goal, plans it, and executes it."""
        logger.info(f"Received user goal: '{goal}'")
        self.context_manager.add_message("user", goal)

        # 1. Gather environmental context
        context_snapshot = self.context_manager.get_snapshot()

        # 2. Plan steps
        available_tools = self.tool_registry.list_tools()
        plan = self.planner.plan(goal, context_snapshot, available_tools)

        # 3. Execute plan
        completed_plan = self.executor.execute_plan(plan)

        # 4. Save result into conversation context
        summary = f"Task completed with {len(completed_plan.steps)} steps." if completed_plan.state.value == "COMPLETED" else f"Task {completed_plan.state.value}: {completed_plan.error}"
        self.context_manager.add_message("assistant", summary)

        return completed_plan

    def stop(self, reason: str = "User initiated emergency stop") -> None:
        """Trigger emergency stop immediately."""
        self.emergency_stop.trigger(reason=reason)

    def reset_stop(self) -> None:
        """Reset emergency stop state."""
        self.emergency_stop.reset()
