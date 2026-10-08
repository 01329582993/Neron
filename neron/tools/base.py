"""Standardized tool interface and execution results for Neron."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolResult:
    """Standardized output returned by every tool."""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }


class BaseTool(ABC):
    """Abstract base class for all agent and plugin tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier of the tool (e.g. 'filesystem.search')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Clear natural language description for LLM tool selection."""
        pass

    @property
    @abstractmethod
    def parameters_schema(self) -> Dict[str, Any]:
        """JSON Schema dictionary describing the expected input arguments."""
        pass

    @property
    @abstractmethod
    def required_capabilities(self) -> List[str]:
        """List of security capability identifiers required to run this tool."""
        pass

    def validate_arguments(self, arguments: Dict[str, Any]) -> bool:
        """Validate input arguments against parameters_schema."""
        schema = self.parameters_schema
        required_fields = schema.get("required", [])
        for field_name in required_fields:
            if field_name not in arguments:
                return False
        return True

    @abstractmethod
    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the tool operation."""
        pass

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> bool:
        """
        Verification Hook: Post-execution check to verify OS state actually changed.
        Defaults to True for read-only tools, overridden for mutations.
        """
        return result.success

    def to_llm_tool_definition(self) -> Dict[str, Any]:
        """Format tool definition into standard OpenAI/Ollama function calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            }
        }
