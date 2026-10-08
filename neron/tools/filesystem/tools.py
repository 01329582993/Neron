"""Standard filesystem manipulation tools with verification hooks."""

import fnmatch
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
from neron.security.permissions import Capability
from neron.tools.base import BaseTool, ToolResult
from neron.utils.logger import get_logger

logger = get_logger("tools.filesystem")


class FilesystemSearchTool(BaseTool):
    """Search for files and directories matching a pattern."""

    @property
    def name(self) -> str:
        return "filesystem.search"

    @property
    def description(self) -> str:
        return "Search for files and folders matching a filename query or wildcard pattern."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Filename, substring, or wildcard pattern to search for."},
                "root_dir": {"type": "string", "description": "Starting directory. Defaults to user home directory or current directory."},
                "max_results": {"type": "integer", "description": "Maximum number of results to return (default 25)."}
            },
            "required": ["query"]
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.FILESYSTEM_READ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        query = arguments.get("query", "").strip()
        root_dir_str = arguments.get("root_dir")
        max_results = arguments.get("max_results", 25)

        start_path = Path(root_dir_str).resolve() if root_dir_str else Path.cwd()
        if not start_path.exists():
            return ToolResult(success=False, output=[], error=f"Directory '{start_path}' does not exist.")

        pattern = f"*{query}*" if not ("*" in query or "?" in query) else query
        matches = []

        try:
            for root, dirs, files in os.walk(start_path):
                # Check directories
                for d in dirs:
                    if fnmatch.fnmatch(d.lower(), pattern.lower()):
                        matches.append({"path": os.path.join(root, d), "type": "directory"})
                        if len(matches) >= max_results:
                            break
                if len(matches) >= max_results:
                    break

                # Check files
                for f in files:
                    if fnmatch.fnmatch(f.lower(), pattern.lower()):
                        matches.append({"path": os.path.join(root, f), "type": "file"})
                        if len(matches) >= max_results:
                            break
                if len(matches) >= max_results:
                    break

            return ToolResult(
                success=True,
                output={"matches": matches, "count": len(matches), "root": str(start_path)}
            )
        except Exception as e:
            return ToolResult(success=False, output=[], error=str(e))


class FilesystemReadTool(BaseTool):
    """Read contents of a text file."""

    @property
    def name(self) -> str:
        return "filesystem.read"

    @property
    def description(self) -> str:
        return "Read the contents of a local text file."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read."},
                "max_bytes": {"type": "integer", "description": "Maximum bytes to read (default 50,000)."}
            },
            "required": ["path"]
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.FILESYSTEM_READ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        path = Path(arguments.get("path", "")).resolve()
        max_bytes = arguments.get("max_bytes", 50000)

        if not path.exists():
            return ToolResult(success=False, output=None, error=f"File not found: {path}")
        if not path.is_file():
            return ToolResult(success=False, output=None, error=f"Path is not a file: {path}")

        try:
            size = path.stat().st_size
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_bytes)
            truncated = size > max_bytes
            return ToolResult(
                success=True,
                output={"content": content, "size_bytes": size, "truncated": truncated, "path": str(path)}
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class FilesystemWriteTool(BaseTool):
    """Create or overwrite a file with verification hook."""

    @property
    def name(self) -> str:
        return "filesystem.write"

    @property
    def description(self) -> str:
        return "Write text content to a file, creating directories if needed."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Target file path."},
                "content": {"type": "string", "description": "Text content to write."},
                "append": {"type": "boolean", "description": "Append to file instead of overwrite (default false)."}
            },
            "required": ["path", "content"]
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.FILESYSTEM_WRITE]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        path = Path(arguments.get("path", "")).resolve()
        content = arguments.get("content", "")
        append = arguments.get("append", False)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
            with open(path, mode, encoding="utf-8") as f:
                f.write(content)
            return ToolResult(
                success=True,
                output={"path": str(path), "bytes_written": len(content.encode("utf-8"))}
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> bool:
        """Verify file exists on disk and is accessible."""
        if not result.success:
            return False
        path = Path(arguments.get("path", "")).resolve()
        return path.exists() and path.is_file()


class FilesystemListTool(BaseTool):
    """List directory contents."""

    @property
    def name(self) -> str:
        return "filesystem.list"

    @property
    def description(self) -> str:
        return "List files and directories in a target folder."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to list."}
            },
            "required": ["path"]
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.FILESYSTEM_READ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        path = Path(arguments.get("path", "")).resolve()
        if not path.exists():
            return ToolResult(success=False, output=None, error=f"Directory does not exist: {path}")
        if not path.is_dir():
            return ToolResult(success=False, output=None, error=f"Path is not a directory: {path}")

        try:
            items = []
            for item in sorted(path.iterdir()):
                items.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size_bytes": item.stat().st_size if item.is_file() else 0,
                })
            return ToolResult(success=True, output={"path": str(path), "items": items, "count": len(items)})
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class FilesystemDeleteTool(BaseTool):
    """Delete a file or directory with verification."""

    @property
    def name(self) -> str:
        return "filesystem.delete"

    @property
    def description(self) -> str:
        return "Delete a file or directory."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to delete."}
            },
            "required": ["path"]
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.FILESYSTEM_DELETE]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        path = Path(arguments.get("path", "")).resolve()
        if not path.exists():
            return ToolResult(success=False, output=None, error=f"Target path does not exist: {path}")

        try:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            return ToolResult(success=True, output=f"Successfully deleted {path}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> bool:
        """Verify target path no longer exists."""
        if not result.success:
            return False
        path = Path(arguments.get("path", "")).resolve()
        return not path.exists()
