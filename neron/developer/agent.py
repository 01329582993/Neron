"""DeveloperAgent master subsystem for codebase introspection and self-improvement."""

from pathlib import Path
import traceback
from typing import Any, Dict, List, Optional, Union

from neron.developer.introspector import CodeIntrospector
from neron.developer.patcher import PatchGenerator, PatchValidationResult, PatchValidator
from neron.developer.scaffolder import PluginScaffoldConfig, PluginScaffolder
from neron.developer.test_runner import TestResult, TestRunner
from neron.utils.logger import get_logger

logger = get_logger("developer.agent")


class DeveloperAgent:
    """
    Subsystem for codebase introspection, automated test execution,
    patch drafting, syntax validation, and plugin scaffolding.
    """

    def __init__(self, root_dir: Optional[Union[str, Path]] = None):
        self.root_dir = Path(root_dir).resolve() if root_dir else Path.cwd().resolve()
        self.introspector = CodeIntrospector(root_dir=self.root_dir)
        self.test_runner = TestRunner(root_dir=self.root_dir)
        self.patch_generator = PatchGenerator()
        self.patch_validator = PatchValidator()
        self.scaffolder = PluginScaffolder(plugins_root=self.root_dir / "plugins")

    def introspect_source(self, target: str) -> Dict[str, Any]:
        """
        Inspect a module name (e.g. 'neron.tools') or a file path.
        """
        path = Path(target)
        if not path.is_absolute():
            candidate = self.root_dir / target
            if candidate.exists():
                path = candidate

        if path.is_file():
            return self.introspector.inspect_file(path)
        return self.introspector.inspect_module(target)

    def find_symbol(self, symbol_name: str, max_results: int = 15) -> List[Dict[str, Any]]:
        """
        Locate functions or classes matching symbol_name across repository.
        """
        return self.introspector.find_symbol(symbol_name, max_results=max_results)

    def validate_code(self, code: str) -> Dict[str, Any]:
        """
        Validate Python syntax of raw code string.
        """
        is_valid, error, line = self.introspector.validate_syntax(code)
        return {
            "is_valid": is_valid,
            "error": error,
            "line": line,
        }

    def run_tests(
        self,
        target: Optional[str] = None,
        timeout: int = 120,
        with_coverage: bool = False,
    ) -> TestResult:
        """
        Run test suite or specific test file.
        """
        return self.test_runner.run_tests(target=target, timeout=timeout, with_coverage=with_coverage)

    def create_patch(
        self,
        target_file: Union[str, Path],
        modified_content: str,
    ) -> PatchValidationResult:
        """
        Generate diff and validate a proposed modification against a file.
        """
        path = Path(target_file)
        if not path.is_absolute():
            path = self.root_dir / target_file
        return self.patch_validator.validate_patch(path, modified_content)

    def scaffold_plugin(
        self,
        plugin_id: str,
        name: str,
        description: str = "",
        tool_name: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """
        Generate complete boilerplate for a new plugin.
        """
        config = PluginScaffoldConfig(
            plugin_id=plugin_id,
            name=name,
            description=description,
            tool_name=tool_name,
            permissions=permissions or ["filesystem.read"],
            output_dir=output_dir,
        )
        created_paths = self.scaffolder.create_plugin_scaffold(config)
        return {
            "status": "success",
            "plugin_id": plugin_id,
            "paths": {k: str(v) for k, v in created_paths.items()},
        }

    def diagnose_failure(self, error_message: str) -> Dict[str, Any]:
        """
        Analyze an error or traceback and provide remediation hints.
        """
        hints = []
        err_lower = error_message.lower()

        if "modulenotfounderror" in err_lower or "no module named" in err_lower:
            hints.append("Missing dependency. Check requirements.txt or run pip install.")
        elif "syntaxerror" in err_lower:
            hints.append("Python syntax violation. Use validate_code to check AST validity.")
        elif "permissiondeniederror" in err_lower or "permission denied" in err_lower:
            hints.append("Capability permission rejected. Check SecurityMode or granted capabilities.")
        elif "timeoutexpired" in err_lower or "timed out" in err_lower:
            hints.append("Operation exceeded timeout limit. Check for infinite loops or network blocks.")
        elif "assertionerror" in err_lower:
            hints.append("Test assertion failed. Review test expectations against actual return value.")
        else:
            hints.append("General runtime error. Check logs and inspect surrounding source code.")

        return {
            "error_analyzed": error_message[:300],
            "hints": hints,
        }
