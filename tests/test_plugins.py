"""Test suite for Neron Stage 10 Plugin Architecture."""

import json
from pathlib import Path
import tempfile
import pytest

from neron.plugins.base import PluginBase, PluginMetadata, PluginState
from neron.plugins.loader import PluginLoader, PluginLoadError
from neron.plugins.manager import PluginManager
from neron.plugins.manifest import InvalidManifestError, PluginManifestValidator
from neron.tools.registry import ToolRegistry


# ── Manifest Tests ──────────────────────────────────────────────────────────

class TestPluginManifest:
    def test_load_valid_yaml_manifest(self, tmp_path):
        manifest_content = """
id: "test-plugin"
name: "Test Plugin"
version: "1.2.3"
author: "Tester"
description: "A test plugin"
permissions:
  - "system.inspect"
tools:
  - name: "test.tool"
    description: "Sample tool"
config:
  setting: "value"
"""
        (tmp_path / "plugin.yaml").write_text(manifest_content, encoding="utf-8")
        meta = PluginManifestValidator.load_manifest(tmp_path)

        assert meta.id == "test-plugin"
        assert meta.name == "Test Plugin"
        assert meta.version == "1.2.3"
        assert meta.permissions == ["system.inspect"]
        assert len(meta.tools) == 1
        assert meta.config["setting"] == "value"

    def test_load_valid_json_manifest(self, tmp_path):
        manifest_data = {
            "id": "json-plugin",
            "name": "JSON Plugin",
            "version": "2.0.0",
            "permissions": ["network.access"],
            "tools": [],
        }
        (tmp_path / "plugin.json").write_text(json.dumps(manifest_data), encoding="utf-8")
        meta = PluginManifestValidator.load_manifest(tmp_path)

        assert meta.id == "json-plugin"
        assert meta.name == "JSON Plugin"
        assert meta.permissions == ["network.access"]

    def test_missing_required_fields_raises_error(self, tmp_path):
        incomplete = "id: 'bad-plugin'\n" # missing name and version
        (tmp_path / "plugin.yaml").write_text(incomplete, encoding="utf-8")

        with pytest.raises(InvalidManifestError):
            PluginManifestValidator.load_manifest(tmp_path)

    def test_nonexistent_directory_raises_error(self, tmp_path):
        with pytest.raises(InvalidManifestError):
            PluginManifestValidator.load_manifest(tmp_path / "nonexistent")


# ── Loader Tests ────────────────────────────────────────────────────────────

class TestPluginLoader:
    def test_load_valid_plugin(self, tmp_path):
        manifest_content = """
id: "dynamic-test"
name: "Dynamic Test"
version: "1.0.0"
entrypoint: "plugin.py"
"""
        (tmp_path / "plugin.yaml").write_text(manifest_content, encoding="utf-8")

        code = """
from neron.plugins.base import PluginBase

class MyDynamicPlugin(PluginBase):
    def on_load(self) -> bool:
        return True
"""
        (tmp_path / "plugin.py").write_text(code, encoding="utf-8")

        meta = PluginManifestValidator.load_manifest(tmp_path)
        instance = PluginLoader.load_plugin_from_metadata(meta)

        assert isinstance(instance, PluginBase)
        assert instance.state == PluginState.LOADED
        assert instance.metadata.id == "dynamic-test"

    def test_load_fails_when_on_load_returns_false(self, tmp_path):
        (tmp_path / "plugin.yaml").write_text("id: 'fail'\nname: 'Fail'\nversion: '1.0'\n", encoding="utf-8")
        code = """
from neron.plugins.base import PluginBase

class FailingPlugin(PluginBase):
    def on_load(self) -> bool:
        return False
"""
        (tmp_path / "plugin.py").write_text(code, encoding="utf-8")

        meta = PluginManifestValidator.load_manifest(tmp_path)
        with pytest.raises(PluginLoadError):
            PluginLoader.load_plugin_from_metadata(meta)

    def test_load_fails_when_no_plugin_class(self, tmp_path):
        (tmp_path / "plugin.yaml").write_text("id: 'noclass'\nname: 'NoClass'\nversion: '1.0'\n", encoding="utf-8")
        (tmp_path / "plugin.py").write_text("x = 42\n", encoding="utf-8")

        meta = PluginManifestValidator.load_manifest(tmp_path)
        with pytest.raises(PluginLoadError):
            PluginLoader.load_plugin_from_metadata(meta)


# ── Manager & Example Plugins Tests ─────────────────────────────────────────

class TestPluginManager:
    def test_discover_example_plugins(self):
        workspace_root = Path(__file__).resolve().parent.parent
        plugins_dir = workspace_root / "plugins"

        mgr = PluginManager(plugin_dirs=[plugins_dir])
        discovered = mgr.discover()

        ids = [m.id for m in discovered]
        assert "neron-system-monitor" in ids
        assert "neron-media-controller" in ids

    def test_enable_and_disable_plugin_lifecycle(self):
        workspace_root = Path(__file__).resolve().parent.parent
        plugins_dir = workspace_root / "plugins"

        registry = ToolRegistry()
        mgr = PluginManager(plugin_dirs=[plugins_dir], registry=registry)

        # Before enable: tool not in registry
        assert not registry.has("sysmon.check_status")

        # Enable plugin
        ok = mgr.enable("neron-system-monitor")
        assert ok is True
        assert registry.has("sysmon.check_status")

        # Execute the injected tool
        res = registry.execute("sysmon.check_status", {})
        assert res.success is True
        assert "status" in res.output
        assert "cpu_percent" in res.output

        # Disable plugin
        disabled_ok = mgr.disable("neron-system-monitor")
        assert disabled_ok is True
        assert not registry.has("sysmon.check_status")

    def test_media_controller_plugin_lifecycle(self):
        workspace_root = Path(__file__).resolve().parent.parent
        plugins_dir = workspace_root / "plugins"

        registry = ToolRegistry()
        mgr = PluginManager(plugin_dirs=[plugins_dir], registry=registry)

        ok = mgr.enable("neron-media-controller")
        assert ok is True
        assert registry.has("media.play_pause")
        assert registry.has("media.next")

        # Disable
        mgr.disable("neron-media-controller")
        assert not registry.has("media.play_pause")
        assert not registry.has("media.next")

    def test_reload_plugin(self):
        workspace_root = Path(__file__).resolve().parent.parent
        plugins_dir = workspace_root / "plugins"

        registry = ToolRegistry()
        mgr = PluginManager(plugin_dirs=[plugins_dir], registry=registry)

        mgr.enable("neron-system-monitor")
        assert registry.has("sysmon.check_status")

        reloaded = mgr.reload("neron-system-monitor")
        assert reloaded is True
        assert registry.has("sysmon.check_status")

    def test_list_plugins(self):
        workspace_root = Path(__file__).resolve().parent.parent
        plugins_dir = workspace_root / "plugins"

        mgr = PluginManager(plugin_dirs=[plugins_dir])
        plugin_list = mgr.list_plugins()

        assert len(plugin_list) >= 2
        names = [p["name"] for p in plugin_list]
        assert "System Monitor Plugin" in names
        assert "Media Playback Controller" in names
