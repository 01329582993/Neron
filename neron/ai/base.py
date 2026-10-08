"""Abstract AI Provider specifications and response models."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional


@dataclass
class LLMMessage:
    """Message turn in conversation."""
    role: str  # "system", "user", "assistant", "tool"
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class ToolCall:
    """Extracted tool call requested by LLM."""
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMResponse:
    """Standardized response from an LLMProvider."""
    content: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    model: str = ""
    duration_ms: float = 0.0
    finish_reason: str = "stop"


class LLMProvider(ABC):
    """Abstract interface for interchangeable local and remote LLM runtimes."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifier of this provider (e.g. 'ollama', 'openai_compatible', 'heuristic')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the backend runtime/endpoint is reachable and ready."""
        pass

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Simple text generation."""
        pass

    @abstractmethod
    def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Chat completion with optional structured tool definitions."""
        pass

    @abstractmethod
    def stream_chat(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> Iterator[str]:
        """Stream response tokens sequentially."""
        pass


class VisionProvider(ABC):
    """Abstract interface for screenshot and multi-modal image reasoning."""

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def analyze_image(self, image_bytes: bytes, prompt: str) -> str:
        pass


class EmbeddingProvider(ABC):
    """Abstract interface for local/remote vector embeddings."""

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        pass
