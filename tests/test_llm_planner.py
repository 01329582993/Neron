"""Unit tests for LLMPlanner with fallback to HeuristicPlanner."""

import pytest
from neron.ai.base import LLMMessage, LLMProvider, LLMResponse, ToolCall
from neron.ai.routing.router import AIRouter
from neron.core.agent.base import NeronAgent
from neron.core.planner.llm_planner import LLMPlanner
from neron.core.state.models import TaskState
from neron.tools import create_default_registry


class MockAIProvider(LLMProvider):
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    @property
    def name(self) -> str:
        return "mock_llm"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs) -> str:
        return "mock"

    def chat(self, messages, tools=None, **kwargs):
        if self.should_fail:
            raise RuntimeError("Simulated model failure")
        # Return structured tool call
        return LLMResponse(
            content="I will check system status.",
            tool_calls=[ToolCall(name="system.telemetry", arguments={})],
            model="mock-model",
        )

    def stream_chat(self, messages, **kwargs):
        yield "mock"


def test_llm_planner_successful_tool_calling():
    router = AIRouter()
    mock_provider = MockAIProvider(should_fail=False)
    router.register_provider(mock_provider)
    router.config.default_provider = "mock_llm"

    planner = LLMPlanner(ai_router=router)
    tools = create_default_registry().list_tools()

    plan = planner.plan(
        goal="check system status",
        context={"platform": "windows", "cwd": "."},
        available_tools=tools,
    )

    assert plan.state == TaskState.PENDING
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "system.telemetry"


def test_llm_planner_fallback_on_model_error():
    router = AIRouter()
    mock_provider = MockAIProvider(should_fail=True)
    router.register_provider(mock_provider)
    router.config.default_provider = "mock_llm"

    planner = LLMPlanner(ai_router=router)
    tools = create_default_registry().list_tools()

    # Even though mock_llm fails with an exception, LLMPlanner must catch it and fallback
    plan = planner.plan(
        goal="what is using all my ram?",
        context={"platform": "windows", "cwd": "."},
        available_tools=tools,
    )

    assert plan.state == TaskState.PENDING
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "system.telemetry"


def test_agent_with_llm_planner_end_to_end():
    agent = NeronAgent()
    # Uses LLMPlanner which selects active provider (heuristic if Ollama offline)
    plan = agent.run_goal("what is using all my ram?")
    assert plan.state == TaskState.COMPLETED
    assert plan.steps[0].state == TaskState.COMPLETED
    assert plan.steps[0].tool_name == "system.telemetry"
