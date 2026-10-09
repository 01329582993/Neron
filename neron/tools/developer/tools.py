"""Developer tools for codebase introspection, testing, and plugin scaffolding."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from neron.developer.agent import DeveloperAgent
from neron.developer.backup import BackupManager
from neron.developer.introspector import CodeIntrospector
from neron.developer.scaffolder import PluginScaffoldConfig, PluginScaffolder
from neron.developer.staging import StagingWorkspace
from neron.developer.test_runner import TestRunner
from neron.developer.updater import SelfUpdatePipeline
from neron.security.permissions import Capability
from neron.tools.base import BaseTool, ToolResult
from neron.utils.logger import get_logger

logger = get_logger("tools.developer")


class DevInspectSourceTool(BaseTool):
    """Inspects Python source files, modules, classes, functions, and docstrings."""

    @property
    def name(self) -> str:
        return "dev.inspect_source"

    @property
    def description(self) -> str:
        return "Inspect Python source files or modules to extract classes, functions, imports, and AST structure."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Module name or file path to inspect."},
                "symbol": {"type": "string", "description": "Optional class or function name to locate."},
            },
            "required": ["target"],
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.FILESYSTEM_READ]

    def __init__(self, introspector: Optional[CodeIntrospector] = None):
        self.introspector = introspector or CodeIntrospector()

    def execute(self, arguments: Optional[Dict[str, Any]] = None, **kwargs: Any) -> ToolResult:
        args = dict(arguments or {})
        args.update(kwargs)

        target = args.get("target", "")
        symbol = args.get("symbol")

        if not target or not target.strip():
            return ToolResult(success=False, output=None, error="Parameter 'target' is required.")

        try:
            if symbol and symbol.strip():
                matches = self.introspector.find_symbol(symbol.strip())
                return ToolResult(
                    success=True,
                    output={"symbol": symbol, "matches": matches, "count": len(matches)},
                )

            # Check if target is a file or module
            path = Path(target)
            if path.is_file() or (not path.is_absolute() and (self.introspector.root_dir / target).is_file()):
                actual_path = path if path.is_file() else (self.introspector.root_dir / target)
                info = self.introspector.inspect_file(actual_path)
            else:
                info = self.introspector.inspect_module(target)

            return ToolResult(
                success=True,
                output=info,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Failed to inspect '{target}': {e}",
            )


class DevRunTestsTool(BaseTool):
    """Runs automated unit tests and integration tests via pytest."""

    @property
    def name(self) -> str:
        return "dev.run_tests"

    @property
    def description(self) -> str:
        return "Executes pytest test suite or a specific test file and parses results."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Optional test file or node to execute."},
                "timeout": {"type": "integer", "description": "Maximum execution time in seconds.", "default": 120},
                "with_coverage": {"type": "boolean", "description": "Evaluate code coverage.", "default": False},
            },
            "required": [],
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.TERMINAL_EXECUTE]

    def __init__(self, test_runner: Optional[TestRunner] = None):
        self.test_runner = test_runner or TestRunner()

    def execute(self, arguments: Optional[Dict[str, Any]] = None, **kwargs: Any) -> ToolResult:
        args = dict(arguments or {})
        args.update(kwargs)

        target = args.get("target")
        timeout = args.get("timeout", 120)
        with_coverage = args.get("with_coverage", False)

        try:
            result = self.test_runner.run_tests(
                target=target,
                timeout=timeout,
                with_coverage=with_coverage,
            )
            return ToolResult(
                success=result.success,
                output=result.to_dict(),
                error=None if result.success else f"Test suite had {result.failed} failures and {result.errors} errors.",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Test runner error: {e}",
            )


class DevValidateCodeTool(BaseTool):
    """Validates Python code syntax without executing it."""

    @property
    def name(self) -> str:
        return "dev.validate_code"

    @property
    def description(self) -> str:
        return "Checks Python source code syntax and returns AST validity and error lines."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source code string to validate."},
            },
            "required": ["code"],
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.FILESYSTEM_READ]

    def __init__(self, introspector: Optional[CodeIntrospector] = None):
        self.introspector = introspector or CodeIntrospector()

    def execute(self, arguments: Optional[Dict[str, Any]] = None, **kwargs: Any) -> ToolResult:
        args = dict(arguments or {})
        args.update(kwargs)

        code = args.get("code")
        if code is None:
            return ToolResult(success=False, output=None, error="Parameter 'code' is required.")

        is_valid, error, line = self.introspector.validate_syntax(code)
        if is_valid:
            return ToolResult(
                success=True,
                output={"is_valid": True, "error": None, "line": None},
            )
        else:
            return ToolResult(
                success=False,
                output={"is_valid": False, "error": error, "line": line},
                error=f"Syntax error at line {line}: {error}",
            )


class DevCreatePluginScaffoldTool(BaseTool):
    """Generates complete scaffolding for a new Neron plugin."""

    @property
    def name(self) -> str:
        return "dev.create_plugin"

    @property
    def description(self) -> str:
        return "Creates boilerplate directories, manifest, tool classes, and unit tests for a new plugin."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "plugin_id": {"type": "string", "description": "Unique plugin identifier (lowercase alphanumeric)."},
                "name": {"type": "string", "description": "Human-readable display name of the plugin."},
                "description": {"type": "string", "description": "Description of plugin capabilities."},
                "tool_name": {"type": "string", "description": "Initial tool name."},
                "permissions": {"type": "array", "items": {"type": "string"}, "description": "Required capability permissions."},
            },
            "required": ["plugin_id", "name"],
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.FILESYSTEM_WRITE]

    def __init__(self, scaffolder: Optional[PluginScaffolder] = None):
        self.scaffolder = scaffolder or PluginScaffolder()

    def execute(self, arguments: Optional[Dict[str, Any]] = None, **kwargs: Any) -> ToolResult:
        args = dict(arguments or {})
        args.update(kwargs)

        plugin_id = args.get("plugin_id")
        name = args.get("name")
        description = args.get("description", "A community extension for Neron.")
        tool_name = args.get("tool_name")
        permissions = args.get("permissions")

        if not plugin_id or not name:
            return ToolResult(success=False, output=None, error="Parameters 'plugin_id' and 'name' are required.")

        try:
            config = PluginScaffoldConfig(
                plugin_id=plugin_id,
                name=name,
                description=description,
                tool_name=tool_name,
                permissions=permissions or ["filesystem.read"],
            )
            created = self.scaffolder.create_plugin_scaffold(config)
            return ToolResult(
                success=True,
                output={"plugin_id": plugin_id, "paths": {k: str(v) for k, v in created.items()}},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Failed to scaffold plugin '{plugin_id}': {e}",
            )


class DevStagePatchTool(BaseTool):
    """Stages a proposed code modification into the isolated staging workspace."""

    @property
    def name(self) -> str:
        return "dev.stage_patch"

    @property
    def description(self) -> str:
        return "Stage a proposed code change into the isolated .neron/staging/workspace/ sandbox."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative project path of the file to stage."},
                "content": {"type": "string", "description": "Full new content for the file."},
            },
            "required": ["file_path", "content"],
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.SELF_MODIFY, Capability.FILESYSTEM_WRITE]

    def __init__(self, staging: Optional[StagingWorkspace] = None):
        self.staging = staging or StagingWorkspace()

    def execute(self, arguments: Optional[Dict[str, Any]] = None, **kwargs: Any) -> ToolResult:
        args = dict(arguments or {})
        args.update(kwargs)

        file_path = args.get("file_path")
        content = args.get("content")

        if not file_path or content is None:
            return ToolResult(success=False, output=None, error="Parameters 'file_path' and 'content' are required.")

        try:
            dest = self.staging.stage_file(file_path, content)
            diffs = self.staging.get_diff_summary()
            return ToolResult(
                success=True,
                output={
                    "staged_file": file_path,
                    "staged_path": str(dest),
                    "diff": diffs.get(file_path.replace("\\", "/"), ""),
                },
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Failed to stage patch for '{file_path}': {e}",
            )


class DevDeployStagedTool(BaseTool):
    """Atomically deploys staged code modifications into production."""

    @property
    def name(self) -> str:
        return "dev.deploy_staged"

    @property
    def description(self) -> str:
        return "Atomically deploy staged code modifications after pre-deployment validation and create a backup checkpoint."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "auto_rollback": {"type": "boolean", "description": "Automatically rollback on post-deployment health check failure.", "default": True},
                "skip_tests": {"type": "boolean", "description": "Skip pre-deployment test execution.", "default": False},
            },
            "required": [],
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.SELF_MODIFY]

    def __init__(self, pipeline: Optional[SelfUpdatePipeline] = None):
        self.pipeline = pipeline or SelfUpdatePipeline()

    def execute(self, arguments: Optional[Dict[str, Any]] = None, **kwargs: Any) -> ToolResult:
        args = dict(arguments or {})
        args.update(kwargs)

        auto_rollback = args.get("auto_rollback", True)
        skip_tests = args.get("skip_tests", False)

        try:
            report = self.pipeline.deploy_atomic(
                require_health_check=True,
                auto_rollback=auto_rollback,
                skip_tests=skip_tests,
            )
            return ToolResult(
                success=report.success,
                output=report.to_dict(),
                error=None if report.success else report.message,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Self-update deployment error: {e}",
            )


class DevRollbackTool(BaseTool):
    """Restores production workspace from a previous backup snapshot."""

    @property
    def name(self) -> str:
        return "dev.rollback"

    @property
    def description(self) -> str:
        return "Instantly restore the production workspace from a previous backup snapshot."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "backup_id": {"type": "string", "description": "Optional specific backup identifier to restore. Defaults to latest."},
            },
            "required": [],
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.SELF_MODIFY]

    def __init__(self, pipeline: Optional[SelfUpdatePipeline] = None):
        self.pipeline = pipeline or SelfUpdatePipeline()

    def execute(self, arguments: Optional[Dict[str, Any]] = None, **kwargs: Any) -> ToolResult:
        args = dict(arguments or {})
        args.update(kwargs)

        backup_id = args.get("backup_id")

        try:
            res = self.pipeline.rollback(backup_id=backup_id)
            return ToolResult(
                success=res.get("success", False),
                output=res,
                error=None if res.get("success") else res.get("message"),
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Rollback error: {e}",
            )
