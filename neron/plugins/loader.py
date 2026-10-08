"""Dynamic module loading and runtime instantiation for Neron plugins."""

import importlib.util
import inspect
from pathlib import Path
import sys
from typing import Optional, Type

from neron.plugins.base import PluginBase, PluginMetadata, PluginState
from neron.utils.logger import get_logger

logger = get_logger("plugins.loader")


class PluginLoadError(Exception):
    """Raised when a plugin fails to import or instantiate."""
    pass


class PluginLoader:
    """
    Safely imports plugin source code from disk and instantiates the PluginBase subclass.
    """

    @classmethod
    def load_plugin_from_metadata(cls, metadata: PluginMetadata) -> PluginBase:
        if not metadata.directory:
            raise PluginLoadError(f"Plugin {metadata.id} has no source directory specified.")

        entry_path = Path(metadata.directory) / metadata.entrypoint
        if not entry_path.is_file():
            raise PluginLoadError(
                f"Entrypoint file '{metadata.entrypoint}' not found in {metadata.directory}"
            )

        module_name = f"neron_plugin_{metadata.id.replace('-', '_')}"

        try:
            # Create importlib spec
            spec = importlib.util.spec_from_file_location(module_name, entry_path)
            if spec is None or spec.loader is None:
                raise PluginLoadError(f"Could not build module spec for {entry_path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Search module for subclass of PluginBase
            plugin_cls: Optional[Type[PluginBase]] = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, PluginBase)
                    and attr is not PluginBase
                ):
                    plugin_cls = attr
                    break

            if not plugin_cls:
                raise PluginLoadError(
                    f"No subclass of PluginBase found in '{metadata.entrypoint}' for plugin '{metadata.id}'"
                )

            instance = plugin_cls(metadata=metadata, config=metadata.config)
            loaded_ok = instance.on_load()
            if not loaded_ok:
                instance.state = PluginState.ERROR
                raise PluginLoadError(f"Plugin '{metadata.id}' on_load() returned False.")

            instance.state = PluginState.LOADED
            logger.info(f"Successfully loaded plugin instance: '{metadata.name}' ({metadata.id})")
            return instance

        except Exception as e:
            logger.error(f"Failed to load plugin '{metadata.id}': {e}")
            raise PluginLoadError(f"Error loading plugin '{metadata.id}': {e}") from e
