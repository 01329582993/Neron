"""Central PluginManager coordinating discovery, lifecycles, and tool registry injection."""

from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Union

from neron.plugins.base import PluginBase, PluginMetadata, PluginState
from neron.plugins.loader import PluginLoader, PluginLoadError
from neron.plugins.manifest import PluginManifestValidator, InvalidManifestError
from neron.security.policy import PermissionManager
from neron.tools.registry import ToolRegistry
from neron.utils.logger import get_logger

logger = get_logger("plugins.manager")


class PluginManager:
    """
    Discovers, validates, loads, and manages the execution lifecycle of Neron plugins.
    """

    def __init__(
        self,
        plugin_dirs: Optional[List[Union[str, Path]]] = None,
        registry: Optional[ToolRegistry] = None,
        permission_manager: Optional[PermissionManager] = None,
    ):
        self._lock = threading.RLock()
        self.registry = registry or ToolRegistry()
        self.permission_manager = permission_manager or PermissionManager()

        # Default search directories
        self.plugin_dirs: List[Path] = []
        if plugin_dirs:
            self.plugin_dirs = [Path(d).resolve() for d in plugin_dirs]
        else:
            # Workspace plugins directory + home config directory
            workspace_plugins = Path(__file__).resolve().parent.parent.parent / "plugins"
            home_plugins = Path.home() / ".neron" / "plugins"
            self.plugin_dirs = [workspace_plugins, home_plugins]

        self._metadata: Dict[str, PluginMetadata] = {}
        self._plugins: Dict[str, PluginBase] = {}

    def add_plugin_directory(self, directory: Union[str, Path]) -> None:
        """Add an additional plugin scan path."""
        with self._lock:
            p = Path(directory).resolve()
            if p not in self.plugin_dirs:
                self.plugin_dirs.append(p)

    def discover(self) -> List[PluginMetadata]:
        """
        Scan all configured plugin directories for valid plugin manifests.
        """
        with self._lock:
            discovered: List[PluginMetadata] = []
            for base_dir in self.plugin_dirs:
                if not base_dir.exists() or not base_dir.is_dir():
                    continue

                for child in base_dir.iterdir():
                    if not child.is_dir():
                        continue
                    try:
                        meta = PluginManifestValidator.load_manifest(child)
                        self._metadata[meta.id] = meta
                        discovered.append(meta)
                        logger.debug(f"Discovered plugin '{meta.id}' at {child}")
                    except InvalidManifestError as e:
                        logger.debug(f"Skipped candidate folder {child.name}: {e}")
                    except Exception as e:
                        logger.warning(f"Error inspecting potential plugin directory {child}: {e}")

            return discovered

    def load(self, plugin_id: str) -> PluginBase:
        """
        Load a discovered plugin into memory.
        """
        with self._lock:
            if plugin_id in self._plugins:
                return self._plugins[plugin_id]

            if plugin_id not in self._metadata:
                self.discover()

            if plugin_id not in self._metadata:
                raise KeyError(f"Plugin '{plugin_id}' not found in any plugin directory.")

            meta = self._metadata[plugin_id]
            instance = PluginLoader.load_plugin_from_metadata(meta)
            self._plugins[plugin_id] = instance
            return instance

    def enable(self, plugin_id: str) -> bool:
        """
        Activate a plugin and inject its exposed tools into the active ToolRegistry.
        """
        with self._lock:
            instance = self.load(plugin_id)
            if instance.state == PluginState.ENABLED:
                return True

            try:
                instance.on_enable(self.registry)
                instance.state = PluginState.ENABLED
                logger.info(f"Plugin '{plugin_id}' enabled successfully.")
                return True
            except Exception as e:
                instance.state = PluginState.ERROR
                logger.error(f"Failed to enable plugin '{plugin_id}': {e}")
                return False

    def disable(self, plugin_id: str) -> bool:
        """
        Deactivate a plugin and unregister its tools from the active ToolRegistry.
        """
        with self._lock:
            if plugin_id not in self._plugins:
                return False

            instance = self._plugins[plugin_id]
            if instance.state != PluginState.ENABLED:
                return True

            try:
                instance.on_disable(self.registry)
                instance.state = PluginState.DISABLED
                logger.info(f"Plugin '{plugin_id}' disabled.")
                return True
            except Exception as e:
                logger.error(f"Error disabling plugin '{plugin_id}': {e}")
                return False

    def reload(self, plugin_id: str) -> bool:
        """
        Disable, re-read manifest, re-instantiate, and re-enable a plugin.
        """
        with self._lock:
            self.disable(plugin_id)
            if plugin_id in self._plugins:
                instance = self._plugins.pop(plugin_id)
                instance.on_unload()

            # Re-discover
            self.discover()
            return self.enable(plugin_id)

    def get_plugin(self, plugin_id: str) -> Optional[PluginBase]:
        with self._lock:
            return self._plugins.get(plugin_id)

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Return formatted summary of all known plugins and their states."""
        with self._lock:
            self.discover()
            results = []
            for pid, meta in self._metadata.items():
                instance = self._plugins.get(pid)
                state = instance.state.value if instance else PluginState.DISCOVERED.value
                results.append({
                    "id": meta.id,
                    "name": meta.name,
                    "version": meta.version,
                    "description": meta.description,
                    "author": meta.author,
                    "state": state,
                    "permissions": meta.permissions,
                    "tools": [t.get("name") for t in meta.tools],
                })
            return results

    def load_and_enable_all(self) -> None:
        """Convenience method to discover and enable all available plugins."""
        with self._lock:
            discovered = self.discover()
            for meta in discovered:
                try:
                    self.enable(meta.id)
                except Exception as e:
                    logger.warning(f"Could not auto-enable plugin '{meta.id}': {e}")
