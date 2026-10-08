"""Unit tests for ExecutionEngine and step state transitions."""

import pytest
from neron.core.events.bus import EventBus
from neron.core.executor.base import ExecutionEngine
from neron.core.state.models import PlanStep, TaskPlan, TaskState
from neron.security.emergency_stop import EmergencyStopCoordinator
from neron.tools import create_default_registry


def test_successful_plan_execution():
    registry = create_default_registry()
    executor = ExecutionEngine(tool_registry=registry)

    plan = TaskPlan(
        goal="Check system load",
        steps=[
            PlanStep(
                tool_name="system.telemetry",
                arguments={},
                description="Check system metrics"
            )
        ]
    )

    result_plan = executor.execute_plan(plan)
    assert result_plan.state == TaskState.COMPLETED
    assert result_plan.steps[0].state == TaskState.COMPLETED
    assert result_plan.steps[0].result is not None


def test_emergency_stop_halts_plan():
    registry = create_default_registry()
    stop_coord = EmergencyStopCoordinator()
    executor = ExecutionEngine(tool_registry=registry, emergency_stop=stop_coord)

    plan = TaskPlan(
        goal="Two-step plan",
        steps=[
            PlanStep(tool_name="system.telemetry", arguments={}, description="Step 1"),
            PlanStep(tool_name="system.telemetry", arguments={}, description="Step 2"),
        ]
    )

    # Trigger emergency stop before execution
    stop_coord.trigger(reason="Test abort")

    result_plan = executor.execute_plan(plan)
    assert result_plan.state == TaskState.CANCELLED
