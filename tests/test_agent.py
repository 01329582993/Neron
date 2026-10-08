"""Integration tests for NeronAgent end-to-end goal execution."""

import pytest
from neron.core.agent.base import NeronAgent
from neron.core.state.models import TaskState


def test_agent_telemetry_goal():
    agent = NeronAgent()
    plan = agent.run_goal("what is using all my ram?")
    assert plan.state == TaskState.COMPLETED
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "system.telemetry"
    assert plan.steps[0].state == TaskState.COMPLETED
    assert "cpu_percent" in plan.steps[0].result


def test_agent_context_persistence():
    agent = NeronAgent()
    agent.run_goal("what is using all my ram?")
    # Check conversation history has recorded the turn
    snapshot = agent.context_manager.get_snapshot()
    assert snapshot["history_turns"] >= 2
