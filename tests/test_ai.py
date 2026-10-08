"""Unit tests for AI providers, routing, and offline degradation."""

import pytest
from neron.ai.base import LLMMessage, LLMResponse, ToolCall
from neron.ai.llm.heuristic import HeuristicProvider
from neron.ai.llm.ollama import OllamaProvider
from neron.ai.llm.openai_compatible import OpenAICompatibleProvider
from neron.ai.routing.router import AIRouter
from neron.config.schema import AIConfig, OllamaConfig, OpenAICompatibleConfig


def test_heuristic_provider_chat_and_tools():
    provider = HeuristicProvider()
    assert provider.name == "heuristic"
    assert provider.is_available() is True

    # 1. Telemetry query detection
    resp = provider.chat([LLMMessage(role="user", content="check my ram and cpu")])
    assert isinstance(resp, LLMResponse)
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "system.telemetry"

    # 2. Open app detection
    resp = provider.chat([LLMMessage(role="user", content="open notepad")])
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "system.open_app"
    assert resp.tool_calls[0].arguments["app_name"] == "notepad"

    # 3. Stream chat test
    chunks = list(provider.stream_chat([LLMMessage(role="user", content="hello")]))
    assert len(chunks) > 0


def test_ai_router_fallback():
    # Configure Ollama pointing to a non-existent port to test automated fallback
    cfg = AIConfig(
        default_provider="ollama",
        auto_offline_fallback=True,
        ollama=OllamaConfig(host="http://localhost:59999"),  # Unreachable port
    )
    router = AIRouter(ai_config=cfg)

    # Active provider should automatically degrade to HeuristicProvider
    active = router.get_active_provider()
    assert active.name == "heuristic"
    assert active.is_available() is True


def test_ai_router_custom_registration():
    router = AIRouter()

    class MockProvider(HeuristicProvider):
        @property
        def name(self) -> str:
            return "mock_ai"

        def is_available(self) -> bool:
            return True

    mock = MockProvider()
    router.register_provider(mock)
    assert router.get_provider("mock_ai") is mock
    assert "mock_ai" in router.list_providers()
