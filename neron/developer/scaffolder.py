"""Plugin boilerplate generator and scaffolding automation for Neron."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union

import yaml

from neron.utils.logger import get_logger

logger = get_logger("developer.scaffolder")


@dataclass
class PluginScaffoldConfig:
    """Configuration options for scaffolding a new Neron plugin."""
    plugin_id: str
    name: str
    version: str = "0.1.0"
    description: str = "A community extension for Neron."
    author: str = "Neron Developer"
    tool_name: Optional[str] = None
    permissions: List[str] = field(default_factory=list)
    output_dir: Optional[Union[str, Path]] = None


class PluginScaffolder:
    """
    Generates complete, verified plugin directory structures with manifests,
    tool implementations, and unit test files.
    """

    ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

    def __init__(self, plugins_root: Optional[Union[str, Path]] = None):
        self.plugins_root = Path(plugins_root).resolve() if plugins_root else (Path.cwd() / "plugins").resolve()

    def create_plugin_scaffold(self, config: PluginScaffoldConfig) -> Dict[str, Path]:
        """
        Generate complete plugin files based on config.

        Returns:
            Dictionary mapping role to file Path (manifest, plugin, test, readme, init).
        """
        raw_id = config.plugin_id.strip().lower()
        if not self.ID_PATTERN.match(raw_id):
            raise ValueError(
                f"Invalid plugin_id '{config.plugin_id}'. Must be lowercase alphanumeric with underscores/hyphens."
            )

        # Determine target directory
        if config.output_dir:
            target_dir = Path(config.output_dir).resolve()
        else:
            target_dir = self.plugins_root / raw_id

        target_dir.mkdir(parents=True, exist_ok=True)

        tool_id = config.tool_name or f"{raw_id.replace('-', '_')}.action"
        tool_class_name = "".join(part.capitalize() for part in tool_id.replace(".", "_").split("_")) + "Tool"
        plugin_class_name = "".join(part.capitalize() for part in raw_id.replace("-", "_").split("_")) + "Plugin"

        # 1. Generate plugin.yaml
        manifest_data = {
            "id": raw_id,
            "name": config.name,
            "version": config.version,
            "description": config.description,
            "author": config.author,
            "entrypoint": "plugin.py",
            "permissions": config.permissions or ["filesystem.read"],
            "tools": [tool_id],
        }
        manifest_path = target_dir / "plugin.yaml"
        manifest_path.write_text(yaml.dump(manifest_data, sort_keys=False), encoding="utf-8")

        # 2. Generate plugin.py
        plugin_py_content = f'''"""Implementation for {config.name} plugin."""

from typing import Any, Dict
from neron.plugins.base import PluginBase
from neron.tools.base import BaseTool, ToolResult
from neron.utils.logger import get_logger

logger = get_logger("plugins.{raw_id.replace('-', '_')}")


class {tool_class_name}(BaseTool):
    """Auto-generated action tool for {config.name}."""

    @property
    def name(self) -> str:
        return "{tool_id}"

    @property
    def description(self) -> str:
        return "{config.description}"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {{"type": "object", "properties": {{}}, "required": []}}

    @property
    def required_capabilities(self) -> list:
        return {manifest_data["permissions"]}

    def execute(self, arguments: Dict[str, Any] = None, **kwargs: Any) -> ToolResult:
        args = arguments if arguments is not None else kwargs
        logger.info(f"Executing {{self.name}} with args: {{args}}")
        return ToolResult(
            success=True,
            output={{"status": "ok", "plugin": "{raw_id}", "received": args}},
        )


class {plugin_class_name}(PluginBase):
    """Main plugin lifecycle controller for {config.name}."""

    def __init__(self, metadata=None, config=None):
        super().__init__(metadata=metadata, config=config)
        self.tool = {tool_class_name}()

    def on_load(self) -> bool:
        logger.info(f"Loading plugin {config.name} ({{self.metadata.version}})")
        return True

    def on_enable(self, registry: Any) -> None:
        registry.register(self.tool)
        logger.info(f"Enabled plugin {config.name}")

    def on_disable(self, registry: Any) -> None:
        registry.unregister("{tool_id}")
        logger.info(f"Disabled plugin {config.name}")

    def on_unload(self) -> None:
        logger.info(f"Unloading plugin {config.name}")
'''
        plugin_path = target_dir / "plugin.py"
        plugin_path.write_text(plugin_py_content, encoding="utf-8")

        # 3. Generate __init__.py
        init_content = f'''"""Package initialization for {config.name}."""

from .{plugin_path.stem} import {plugin_class_name}, {tool_class_name}

__all__ = ["{plugin_class_name}", "{tool_class_name}"]
'''
        init_path = target_dir / "__init__.py"
        init_path.write_text(init_content, encoding="utf-8")

        # 4. Generate test file
        test_content = f'''"""Unit tests for {config.name} plugin."""

from pathlib import Path
from neron.plugins.manifest import PluginManifestValidator
from neron.plugins.loader import PluginLoader


def test_{raw_id.replace('-', '_')}_manifest():
    plugin_dir = Path(__file__).parent
    metadata = PluginManifestValidator.load_manifest(plugin_dir)
    assert metadata.id == "{raw_id}"
    assert metadata.name == "{config.name}"
    assert "{tool_id}" in metadata.tools


def test_{raw_id.replace('-', '_')}_lifecycle():
    plugin_dir = Path(__file__).parent
    metadata = PluginManifestValidator.load_manifest(plugin_dir)
    plugin = PluginLoader.load_plugin_from_metadata(metadata)
    assert plugin.on_load() is True
    assert plugin.tool.name == "{tool_id}"
    result = plugin.tool.execute({{"sample_arg": "test"}})
    assert result.success is True
    plugin.on_unload()
'''
        test_path = target_dir / f"test_{raw_id.replace('-', '_')}.py"
        test_path.write_text(test_content, encoding="utf-8")

        # 5. Generate README.md
        readme_content = f'''# {config.name}

> {config.description}

## Overview
- **Plugin ID**: `{raw_id}`
- **Version**: `{config.version}`
- **Author**: `{config.author}`

## Exposed Tools
- `{tool_id}`: Auto-generated action tool.

## Permissions Required
{chr(10).join(f"- `{p}`" for p in manifest_data["permissions"])}
'''
        readme_path = target_dir / "README.md"
        readme_path.write_text(readme_content, encoding="utf-8")

        logger.info(f"Successfully scaffolded plugin '{raw_id}' in {target_dir}")

        return {
            "directory": target_dir,
            "manifest": manifest_path,
            "plugin": plugin_path,
            "init": init_path,
            "test": test_path,
            "readme": readme_path,
        }
