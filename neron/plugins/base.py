"""Base contracts and data models for Neron plugins."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from neron.tools.registry import ToolRegistry

from neron.utils.logger import get_logger



class PluginState(Enum):
    DISCOVERED = "DISCOVERED"
    LOADED = "LOADED"
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    ERROR = "ERROR"


@dataclass
class PluginMetadata:
    """Declared metadata and security permissions of a plugin."""
    id: str
    name: str
    version: str
    description: str = ""
    author: str = "Unknown"
    min_neron_version: str = "0.1.0"
    permissions: List[str] = field(default_factory=list)
    tools: List[Dict[str, Any]] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    entrypoint: str = "plugin.py"
    directory: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "min_neron_version": self.min_neron_version,
            "permissions": self.permissions,
            "tools": self.tools,
            "config": self.config,
            "directory": self.directory,
        }


class PluginBase(ABC):
    """
    Abstract base class for all third-party and community Neron plugins.

    Plugins hook into the Neron runtime, registering and unregistering tools
    dynamically as their lifecycle transitions.
    """

    def __init__(
        self,
        metadata: Optional[PluginMetadata] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.metadata = metadata or PluginMetadata(id="unknown", name="Unknown", version="0.1.0")
        self.config = config or (self.metadata.config if self.metadata else {})
        self.state = PluginState.DISCOVERED
        self.logger = get_logger(f"plugin.{self.metadata.id}")

    def on_load(self) -> bool:
        """
        Called when the plugin is discovered and imported into memory.
        Return True to acknowledge successful load, False to abort.
        """
        self.logger.debug(f"Plugin '{self.metadata.name}' loaded.")
        return True

    def on_enable(self, registry: "ToolRegistry") -> None:
        """
        Called when the plugin is activated by user or policy.
        Register exposed tools with the provided ToolRegistry.
        """
        self.logger.info(f"Plugin '{self.metadata.name}' enabled.")

    def on_disable(self, registry: "ToolRegistry") -> None:

        """
        Called when the plugin is deactivated.
        Clean up and unregister all tools from ToolRegistry.
        """
        self.logger.info(f"Plugin '{self.metadata.name}' disabled.")

    def on_unload(self) -> None:
        """
        Called prior to module eviction or shutdown.
        Release any held file descriptors, background threads, or network sockets.
        """
        self.logger.debug(f"Plugin '{self.metadata.name}' unloaded.")
