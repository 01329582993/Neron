"""Manifest parsing and schema validation for Neron plugins."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from neron.plugins.base import PluginMetadata
from neron.utils.logger import get_logger

logger = get_logger("plugins.manifest")


class InvalidManifestError(Exception):
    """Raised when a plugin manifest is missing, corrupt, or invalid."""
    pass


class PluginManifestValidator:
    """
    Parses and validates plugin manifests (supporting both plugin.yaml and plugin.json).
    """

    REQUIRED_FIELDS = ["id", "name", "version"]

    @classmethod
    def load_manifest(cls, plugin_dir: Union[str, Path]) -> PluginMetadata:
        """
        Locate and parse plugin manifest file in the target directory.
        """
        p = Path(plugin_dir).resolve()
        if not p.is_dir():
            raise InvalidManifestError(f"Plugin directory does not exist: {p}")

        manifest_file = None
        for candidate in ["plugin.yaml", "plugin.yml", "plugin.json"]:
            cand_path = p / candidate
            if cand_path.is_file():
                manifest_file = cand_path
                break

        if not manifest_file:
            raise InvalidManifestError(
                f"No plugin manifest found in {p}. Expected plugin.yaml or plugin.json."
            )

        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                if manifest_file.suffix.lower() == ".json":
                    data = json.load(f)
                else:
                    data = yaml.safe_load(f)
        except Exception as e:
            raise InvalidManifestError(f"Failed to parse {manifest_file.name}: {e}") from e

        if not isinstance(data, dict):
            raise InvalidManifestError(f"Manifest in {manifest_file.name} must be a dictionary/object.")

        # Check required fields
        for req in cls.REQUIRED_FIELDS:
            if req not in data or not str(data[req]).strip():
                raise InvalidManifestError(
                    f"Manifest {manifest_file.name} missing required field: '{req}'"
                )

        # Validate types
        permissions = data.get("permissions", [])
        if not isinstance(permissions, list):
            raise InvalidManifestError("Field 'permissions' must be a list of strings.")

        tools = data.get("tools", [])
        if not isinstance(tools, list):
            raise InvalidManifestError("Field 'tools' must be a list.")

        config = data.get("config", {})
        if not isinstance(config, dict):
            raise InvalidManifestError("Field 'config' must be a dictionary.")

        return PluginMetadata(
            id=str(data["id"]).strip(),
            name=str(data["name"]).strip(),
            version=str(data["version"]).strip(),
            description=str(data.get("description", "")).strip(),
            author=str(data.get("author", "Unknown")).strip(),
            min_neron_version=str(data.get("min_neron_version", "0.1.0")).strip(),
            permissions=[str(p).strip() for p in permissions],
            tools=tools,
            config=config,
            entrypoint=str(data.get("entrypoint", "plugin.py")).strip(),
            directory=str(p),
        )
