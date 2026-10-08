"""Generic OpenAI-compatible LLM provider for local servers (LM Studio, vLLM) and cloud APIs."""

import json
import time
from typing import Any, Dict, Iterator, List, Optional
import requests

from neron.ai.base import LLMMessage, LLMProvider, LLMResponse, ToolCall
from neron.utils.logger import get_logger

logger = get_logger("ai.llm.openai_compatible")


class OpenAICompatibleProvider(LLMProvider):
    """Provider connecting to standard /v1/chat/completions endpoints."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        api_key: str = "",
        model: str = "default",
        timeout: int = 30,
        temperature: float = 0.2,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.temperature = temperature

    @property
    def name(self) -> str:
        return "openai_compatible"

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def is_available(self) -> bool:
        """Check if target server is responding."""
        try:
            resp = requests.get(f"{self.base_url}/models", headers=self._headers(), timeout=2.0)
            return resp.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, **kwargs) -> str:
        resp = self.chat([LLMMessage(role="user", content=prompt)], **kwargs)
        return resp.content

    def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        start_time = time.time()
        url = f"{self.base_url}/chat/completions"

        payload: Dict[str, Any] = {
            "model": kwargs.get("model", self.model),
            "messages": [m.to_dict() for m in messages],
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": False,
        }

        if tools:
            payload["tools"] = tools

        try:
            resp = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            duration_ms = (time.time() - start_time) * 1000

            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            raw_content = msg.get("content") or ""

            tool_calls: List[ToolCall] = []
            for tc in msg.get("tool_calls", []):
                fn = tc.get("function", {})
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {"raw": args}
                tool_calls.append(
                    ToolCall(
                        name=fn.get("name", ""),
                        arguments=args
                    )
                )

            return LLMResponse(
                content=raw_content,
                tool_calls=tool_calls,
                model=data.get("model", self.model),
                duration_ms=round(duration_ms, 2),
                finish_reason=choice.get("finish_reason", "stop"),
            )
        except Exception as e:
            logger.error(f"OpenAICompatible chat error: {e}")
            raise

    def stream_chat(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> Iterator[str]:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [m.to_dict() for m in messages],
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": True,
        }

        with requests.post(url, headers=self._headers(), json=payload, stream=True, timeout=self.timeout) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: ") and not decoded.startswith("data: [DONE]"):
                        try:
                            chunk = json.loads(decoded[6:])
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                yield token
                        except Exception:
                            continue
