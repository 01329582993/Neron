"""Network tools exposing connectivity status, web search, and webpage reading."""

from typing import Any, Dict, List, Optional

from neron.network.browser import WebReader
from neron.network.observer import NetworkObserver
from neron.network.search import SearchEngineRouter
from neron.security.permissions import Capability
from neron.tools.base import BaseTool, ToolResult


class NetworkStatusTool(BaseTool):
    """Tool to check current internet reachability and latency."""

    def __init__(self, observer: Optional[NetworkObserver] = None):
        self.observer = observer or NetworkObserver()

    @property
    def name(self) -> str:
        return "network.status"

    @property
    def description(self) -> str:
        return "Check active internet connectivity status and network round-trip latency."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "force": {"type": "boolean", "description": "Bypass cache to re-probe connection directly.", "default": False},
            },
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.NETWORK_ACCESS]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        force = bool(arguments.get("force", False))
        status = self.observer.check_connection(force=force)
        return ToolResult(
            success=True,
            output=status,
        )


class NetworkSearchTool(BaseTool):
    """Tool to search the web using pluggable search engine."""

    def __init__(self, router: Optional[SearchEngineRouter] = None):
        self.router = router or SearchEngineRouter()

    @property
    def name(self) -> str:
        return "network.search"

    @property
    def description(self) -> str:
        return "Search the web for up-to-date facts, current events, and online information."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Web search query or keywords."},
                "max_results": {"type": "integer", "description": "Maximum number of results (default: 5).", "default": 5},
            },
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.NETWORK_ACCESS]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        query = arguments.get("query", "").strip()
        max_results = int(arguments.get("max_results", 5))

        if not query:
            return ToolResult(success=False, output=None, error="Search query cannot be empty.")

        try:
            results = self.router.search(query=query, max_results=max_results)
            return ToolResult(
                success=True,
                output={
                    "query": query,
                    "count": len(results),
                    "results": [r.to_dict() for r in results],
                },
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Search failed: {e}")


class NetworkFetchPageTool(BaseTool):
    """Tool to fetch and extract readable text from any URL."""

    def __init__(self, reader: Optional[WebReader] = None):
        self.reader = reader or WebReader()

    @property
    def name(self) -> str:
        return "network.fetch_page"

    @property
    def description(self) -> str:
        return "Fetch and extract readable text content and hyperlinks from a webpage URL."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "required": ["url"],
            "properties": {
                "url": {"type": "string", "description": "Full HTTP or HTTPS URL to read."},
                "max_length": {"type": "integer", "description": "Maximum character length of returned text.", "default": 5000},
            },
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.NETWORK_ACCESS]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        url = arguments.get("url", "").strip()
        max_length = int(arguments.get("max_length", 5000))

        if not url:
            return ToolResult(success=False, output=None, error="URL cannot be empty.")

        try:
            content = self.reader.fetch(url=url, max_length=max_length)
            return ToolResult(
                success=content.status_code < 400,
                output=content.to_dict(),
                error=None if content.status_code < 400 else f"HTTP error {content.status_code}",
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Failed to fetch webpage: {e}")
