"""Ollama local AI model provider."""

import json
import time
from typing import Any, Dict, Iterator, List, Optional
import requests

from neron.ai.base import LLMMessage, LLMProvider, LLMResponse, ToolCall
from neron.utils.logger import get_logger

logger = get_logger("ai.llm.ollama")


class OllamaProvider(LLMProvider):
    """Local LLM inference provider using Ollama REST API."""

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "llama3.2:3b",
        timeout: int = 30,
        temperature: float = 0.2,
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature

    @property
    def name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        """Check if local Ollama daemon is reachable."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=1.5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_installed_models(self) -> List[str]:
        """Fetch list of local model names installed in Ollama."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                return [m.get("name") for m in data.get("models", []) if m.get("name")]
        except Exception as e:
            logger.debug(f"Failed to query Ollama models: {e}")
        return []

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from a prompt."""
        url = f"{self.host}/api/generate"
        payload = {
            "model": kwargs.get("model", self.model),
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": kwargs.get("temperature", self.temperature)},
        }
        resp = requests.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json().get("response", "")

    def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Chat completion with optional structured tool schemas."""
        start_time = time.time()
        url = f"{self.host}/api/chat"

        formatted_messages = [m.to_dict() for m in messages]
        payload: Dict[str, Any] = {
            "model": kwargs.get("model", self.model),
            "messages": formatted_messages,
            "stream": False,
            "options": {"temperature": kwargs.get("temperature", self.temperature)},
        }

        if tools:
            payload["tools"] = tools

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            duration_ms = (time.time() - start_time) * 1000

            msg_data = data.get("message", {})
            raw_content = msg_data.get("content", "")

            # Parse tool calls from Ollama native tool calling response
            tool_calls: List[ToolCall] = []
            raw_tool_calls = msg_data.get("tool_calls", [])
            for tc in raw_tool_calls:
                fn = tc.get("function", {})
                tool_calls.append(
                    ToolCall(
                        name=fn.get("name", ""),
                        arguments=fn.get("arguments", {})
                    )
                )

            return LLMResponse(
                content=raw_content,
                tool_calls=tool_calls,
                model=data.get("model", self.model),
                duration_ms=round(duration_ms, 2),
                finish_reason=data.get("done_reason", "stop"),
            )
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            raise

    def stream_chat(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> Iterator[str]:
        """Stream response tokens line-by-line."""
        url = f"{self.host}/api/chat"
        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [m.to_dict() for m in messages],
            "stream": True,
            "options": {"temperature": kwargs.get("temperature", self.temperature)},
        }
        with requests.post(url, json=payload, stream=True, timeout=self.timeout) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    chunk = json.loads(line.decode("utf-8"))
                    msg = chunk.get("message", {})
                    token = msg.get("content", "")
                    if token:
                        yield token
