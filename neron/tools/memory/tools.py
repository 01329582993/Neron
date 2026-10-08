"""Tools for interacting with Neron persistent memory."""

from typing import Any, Dict, List, Optional

from neron.memory.manager import MemoryManager
from neron.security.permissions import Capability
from neron.tools.base import BaseTool, ToolResult


class MemoryRememberTool(BaseTool):
    """Stores a fact, preference, or piece of information into persistent memory."""

    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        self.memory = memory_manager or MemoryManager()

    @property
    def name(self) -> str:
        return "memory.remember"

    @property
    def description(self) -> str:
        return "Store a fact, preference, or knowledge note into persistent memory."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "required": ["key", "value"],
            "properties": {
                "key": {"type": "string", "description": "Subject or key name of the fact (e.g. 'favorite_browser')."},
                "value": {"type": "string", "description": "Value or detail to remember (e.g. 'Firefox')."},
                "category": {"type": "string", "description": "Category for the fact (default: 'general').", "default": "general"},
            },
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.FILESYSTEM_WRITE]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        key = arguments.get("key", "").strip()
        value = arguments.get("value")
        category = arguments.get("category", "general").strip()

        if not key:
            return ToolResult(success=False, output=None, error="Parameter 'key' cannot be empty.")

        try:
            self.memory.remember(key=key, value=value, category=category)
            return ToolResult(
                success=True,
                output={
                    "saved": True,
                    "category": category,
                    "key": key,
                    "value": value,
                },
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Failed to store fact: {e}")


class MemoryRecallTool(BaseTool):
    """Recalls facts or searches persistent memory by key or search query."""

    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        self.memory = memory_manager or MemoryManager()

    @property
    def name(self) -> str:
        return "memory.recall"

    @property
    def description(self) -> str:
        return "Recall stored facts, user preferences, or knowledge by key or search query."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Exact key to retrieve."},
                "query": {"type": "string", "description": "Search string to look up across stored facts."},
                "category": {"type": "string", "description": "Optional category filter."},
            },
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.FILESYSTEM_READ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        key = arguments.get("key")
        query = arguments.get("query")
        category = arguments.get("category")

        try:
            if key:
                val = self.memory.recall(key=key, category=category)
                if val is not None:
                    return ToolResult(success=True, output={"key": key, "value": val, "found": True})
                return ToolResult(success=True, output={"key": key, "value": None, "found": False})

            if query:
                results = self.memory.search(query=query, category=category)
                return ToolResult(success=True, output={"query": query, "results": results, "count": len(results)})

            # If neither key nor query specified, list all facts in category
            all_facts = self.memory.list_facts(category=category)
            return ToolResult(success=True, output={"results": all_facts, "count": len(all_facts)})
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Recall failed: {e}")


class MemoryForgetTool(BaseTool):
    """Deletes a fact from persistent memory."""

    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        self.memory = memory_manager or MemoryManager()

    @property
    def name(self) -> str:
        return "memory.forget"

    @property
    def description(self) -> str:
        return "Delete a fact from persistent memory by key."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "required": ["key"],
            "properties": {
                "key": {"type": "string", "description": "Key of the fact to remove."},
                "category": {"type": "string", "description": "Optional category of the fact."},
            },
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.FILESYSTEM_WRITE]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        key = arguments.get("key", "").strip()
        category = arguments.get("category")

        if not key:
            return ToolResult(success=False, output=None, error="Parameter 'key' cannot be empty.")

        try:
            deleted = self.memory.forget(key=key, category=category)
            return ToolResult(
                success=True,
                output={"deleted": deleted, "key": key},
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Failed to delete fact: {e}")
