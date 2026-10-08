"""Unit tests for HeuristicPlanner intent decomposition."""

import pytest
from neron.core.planner.base import HeuristicPlanner
from neron.core.state.models import TaskState


def test_planner_telemetry_goal():
    planner = HeuristicPlanner()
    plan = planner.plan(
        goal="what is using all my ram?",
        context={"platform": "windows"},
        available_tools=[]
    )
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "system.telemetry"


def test_planner_open_app():
    planner = HeuristicPlanner()
    plan = planner.plan(
        goal="open chrome",
        context={"platform": "windows"},
        available_tools=[]
    )
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "system.open_app"
    assert plan.steps[0].arguments["app_name"] == "chrome"


def test_planner_volume_command():
    planner = HeuristicPlanner()
    plan = planner.plan(
        goal="set volume to 65",
        context={"platform": "windows"},
        available_tools=[]
    )
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "system.volume"
    assert plan.steps[0].arguments["level"] == 65


def test_planner_multi_step_workflow():
    planner = HeuristicPlanner()
    plan = planner.plan(
        goal="prepare development environment",
        context={"platform": "windows"},
        available_tools=[]
    )
    assert len(plan.steps) >= 2
    tool_names = [s.tool_name for s in plan.steps]
    assert "system.open_app" in tool_names
    assert "system.telemetry" in tool_names
