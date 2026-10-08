"""Zero-dependency heuristic fallback provider for guaranteed offline operations."""

import re
import time
from typing import Any, Dict, Iterator, List, Optional

from neron.ai.base import LLMMessage, LLMProvider, LLMResponse, ToolCall
from neron.utils.logger import get_logger

logger = get_logger("ai.llm.heuristic")


class HeuristicProvider(LLMProvider):
    """Fallback reasoning provider using local deterministic pattern matching."""

    @property
    def name(self) -> str:
        return "heuristic"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs) -> str:
        return f"[Heuristic Response] Processed query: {prompt}"

    def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        start_time = time.time()
        last_user_msg = ""
        for m in reversed(messages):
            if m.role == "user":
                last_user_msg = m.content
                break

        lower = last_user_msg.lower()
        tool_calls: List[ToolCall] = []

        # Intent detection
        if any(kw in lower for kw in ["ram", "cpu", "telemetry", "hardware", "system status"]):
            tool_calls.append(ToolCall(name="system.telemetry", arguments={}))

        elif "set volume to" in lower:
            m = re.search(r"set volume to (\d+)", lower)
            if m:
                tool_calls.append(ToolCall(name="system.volume", arguments={"level": int(m.group(1))}))

        elif "volume" in lower:
            tool_calls.append(ToolCall(name="system.volume", arguments={}))

        elif any(kw in lower for kw in ["open", "launch", "start"]):
            m = re.search(r"(?:open|launch|start)\s+([a-zA-Z0-9_\-\.]+)", lower)
            if m and not ("folder" in lower or "file" in lower):
                app_name = m.group(1).strip()
                tool_calls.append(ToolCall(name="system.open_app", arguments={"app_name": app_name}))

        elif any(kw in lower for kw in ["close", "kill", "quit"]):
            m = re.search(r"(?:close|kill|quit)\s+([a-zA-Z0-9_\-\.]+)", lower)
            if m and not ("folder" in lower or "file" in lower):
                app_name = m.group(1).strip()
                tool_calls.append(ToolCall(name="system.close_app", arguments={"app_name": app_name}))

        elif any(kw in lower for kw in ["find", "search", "where is"]):
            query = re.sub(r"^(?:find|search(?:\s+for)?|where\s+is)\s+", "", lower).strip()
            tool_calls.append(ToolCall(name="filesystem.search", arguments={"query": query}))

        duration_ms = (time.time() - start_time) * 1000
        content = "Identified action plan." if tool_calls else f"Understood: '{last_user_msg}'"

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            model="heuristic-engine",
            duration_ms=round(duration_ms, 2),
            finish_reason="stop",
        )

    def stream_chat(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> Iterator[str]:
        resp = self.chat(messages, **kwargs)
        for word in resp.content.split(" "):
            yield word + " "
