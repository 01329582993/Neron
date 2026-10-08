"""Unit tests for ToolRegistry and built-in filesystem/system tools."""

import tempfile
from pathlib import Path
import pytest
from neron.security.policy import PermissionManager
from neron.tools import create_default_registry
from neron.tools.filesystem.tools import (
    FilesystemDeleteTool,
    FilesystemListTool,
    FilesystemReadTool,
    FilesystemWriteTool,
)
from neron.tools.registry import ToolNotFoundError, ToolValidationError


def test_tool_registry_registration():
    registry = create_default_registry()
    assert registry.has("filesystem.search")
    assert registry.has("filesystem.read")
    assert registry.has("filesystem.write")
    assert registry.has("terminal.execute")
    assert registry.has("system.telemetry")

    schemas = registry.list_schemas()
    assert len(schemas) >= 8
    assert any(s["function"]["name"] == "filesystem.search" for s in schemas)


def test_tool_validation_error():
    registry = create_default_registry()
    # Missing required argument 'path'
    with pytest.raises(ToolValidationError):
        registry.execute("filesystem.read", {})


def test_tool_not_found():
    registry = create_default_registry()
    with pytest.raises(ToolNotFoundError):
        registry.execute("non_existent_tool", {})


def test_filesystem_tools_lifecycle(tmp_path):
    registry = create_default_registry()
    test_file = tmp_path / "hello.txt"

    # 1. Write Tool
    write_res = registry.execute(
        "filesystem.write",
        {"path": str(test_file), "content": "Hello from Neron Test!"}
    )
    assert write_res.success is True
    assert write_res.metadata.get("verified") is True
    assert test_file.exists()

    # 2. Read Tool
    read_res = registry.execute(
        "filesystem.read",
        {"path": str(test_file)}
    )
    assert read_res.success is True
    assert read_res.output["content"] == "Hello from Neron Test!"

    # 3. List Tool
    list_res = registry.execute(
        "filesystem.list",
        {"path": str(tmp_path)}
    )
    assert list_res.success is True
    assert any(item["name"] == "hello.txt" for item in list_res.output["items"])

    # 4. Delete Tool (needs permission confirmation in STANDARD mode, so configure prompt)
    registry.permission_manager.set_prompt_handler(lambda req: True)
    delete_res = registry.execute(
        "filesystem.delete",
        {"path": str(test_file)}
    )
    assert delete_res.success is True
    assert delete_res.metadata.get("verified") is True
    assert not test_file.exists()
