"""Exhaustive tests for Stage 13: DeveloperAgent, CodeIntrospector, TestRunner, Patching, and Scaffolding."""

from pathlib import Path
import subprocess
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from neron.core.planner.dag_planner import DAGPlanner
from neron.developer import (
    CodeIntrospector,
    DeveloperAgent,
    PatchGenerator,
    PatchValidationResult,
    PatchValidator,
    PluginScaffoldConfig,
    PluginScaffolder,
    TestResult,
    TestRunner,
)
from neron.plugins.loader import PluginLoader
from neron.plugins.manifest import PluginManifestValidator
from neron.tools import create_default_registry
from neron.tools.developer.tools import (
    DevCreatePluginScaffoldTool,
    DevInspectSourceTool,
    DevRunTestsTool,
    DevValidateCodeTool,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. CodeIntrospector Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCodeIntrospector:

    def test_validate_syntax_valid(self):
        introspector = CodeIntrospector()
        valid, err, line = introspector.validate_syntax("x = 42\ndef hello():\n    return 'world'\n")
        assert valid is True
        assert err is None
        assert line is None

    def test_validate_syntax_invalid(self):
        introspector = CodeIntrospector()
        valid, err, line = introspector.validate_syntax("def broken(\n    return 42\n")
        assert valid is False
        assert err is not None
        assert line is not None

    def test_validate_syntax_empty_and_whitespace(self):
        introspector = CodeIntrospector()
        assert introspector.validate_syntax("")[0] is True
        assert introspector.validate_syntax("   \n\t  ")[0] is True

    def test_inspect_file_structure(self, tmp_path):
        sample_code = '''"""Sample module docstring."""

import os
from math import sqrt

GLOBAL_CONST = 100

class Calculator:
    """A sample calculator."""
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

async def fetch_data(url: str):
    """Fetch async data."""
    pass
'''
        py_file = tmp_path / "sample.py"
        py_file.write_text(sample_code, encoding="utf-8")

        introspector = CodeIntrospector(root_dir=tmp_path)
        info = introspector.inspect_file(py_file)

        assert info["is_valid_syntax"] is True
        assert info["module_docstring"] == "Sample module docstring."
        assert len(info["classes"]) == 1
        assert info["classes"][0]["name"] == "Calculator"
        assert info["classes"][0]["docstring"] == "A sample calculator."
        assert len(info["classes"][0]["methods"]) == 1
        assert info["classes"][0]["methods"][0]["name"] == "add"

        assert len(info["functions"]) == 1
        assert info["functions"][0]["name"] == "fetch_data"
        assert info["functions"][0]["is_async"] is True

        assert "os" in info["imports"]
        assert "math.sqrt" in info["imports"]

    def test_inspect_file_syntax_error(self, tmp_path):
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("class Unclosed:\n  def foo(", encoding="utf-8")

        introspector = CodeIntrospector()
        info = introspector.inspect_file(bad_file)
        assert info["is_valid_syntax"] is False
        assert info["syntax_error"] is not None
        assert info["classes"] == []

    def test_inspect_file_not_found(self):
        introspector = CodeIntrospector()
        with pytest.raises(FileNotFoundError):
            introspector.inspect_file("nonexistent_path_file_123.py")

    def test_inspect_module_known_module(self):
        introspector = CodeIntrospector()
        info = introspector.inspect_module("neron.security.permissions")
        assert info["is_valid_syntax"] is True
        class_names = [c["name"] for c in info["classes"]]
        assert "Capability" in class_names
        assert "SecurityMode" in class_names

    def test_inspect_module_not_found(self):
        introspector = CodeIntrospector()
        with pytest.raises(ModuleNotFoundError):
            introspector.inspect_module("neron.definitely.does.not.exist.module_xyz")

    def test_find_symbol(self, tmp_path):
        file1 = tmp_path / "mod1.py"
        file1.write_text("class TargetEntity:\n    pass\n", encoding="utf-8")

        file2 = tmp_path / "mod2.py"
        file2.write_text("def TargetEntity():\n    return 42\n", encoding="utf-8")

        introspector = CodeIntrospector(root_dir=tmp_path)
        matches = introspector.find_symbol("TargetEntity", search_dir=tmp_path)
        assert len(matches) == 2
        types = {m["type"] for m in matches}
        assert "class" in types
        assert "function" in types

    def test_get_source_lines(self, tmp_path):
        sample = tmp_path / "lines.py"
        sample.write_text("line 1\nline 2\nline 3\nline 4\nline 5\n", encoding="utf-8")

        introspector = CodeIntrospector()
        content = introspector.get_source_lines(sample, 2, 4)
        assert content == "line 2\nline 3\nline 4"


# ─────────────────────────────────────────────────────────────────────────────
# 2. TestRunner & Parsing Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTestRunner:

    def test_parse_pytest_output_all_passed(self):
        output = "tests/test_core.py .... [100%]\n======================= 214 passed in 72.22s ========================"
        runner = TestRunner()
        res = runner.parse_pytest_output(output, exit_code=0)

        assert res.success is True
        assert res.passed == 214
        assert res.failed == 0
        assert res.skipped == 0
        assert res.errors == 0
        assert res.total == 214
        assert res.duration_seconds == 72.22

    def test_parse_pytest_output_with_failures(self):
        output = """
FAILED tests/test_foo.py::test_bar - AssertionError: Expected 1 got 2
FAILED tests/test_baz.py::test_qux - RuntimeError: Crash
=================== 2 failed, 15 passed, 1 skipped in 4.50s ===================="""
        runner = TestRunner()
        res = runner.parse_pytest_output(output, exit_code=1)

        assert res.success is False
        assert res.passed == 15
        assert res.failed == 2
        assert res.skipped == 1
        assert res.total == 18
        assert res.duration_seconds == 4.5
        assert len(res.error_summary) == 2

    def test_parse_pytest_output_with_errors(self):
        output = """
ERROR tests/test_init.py - ImportError: Cannot import name 'X'
======================= 1 error, 5 passed in 0.85s ========================"""
        runner = TestRunner()
        res = runner.parse_pytest_output(output, exit_code=1)

        assert res.success is False
        assert res.errors == 1
        assert res.passed == 5
        assert res.total == 6

    def test_parse_pytest_output_with_coverage(self):
        output = """
tests/test_x.py . [100%]
---------- coverage: platform win32, python 3.11 -----------
Name                     Stmts   Miss  Cover
--------------------------------------------
neron/core/agent.py         50      6    88%
TOTAL                      100     12    88%
======================= 1 passed in 1.20s ========================"""
        runner = TestRunner()
        res = runner.parse_pytest_output(output, exit_code=0)

        assert res.success is True
        assert res.coverage_percent == 88.0

    @patch("subprocess.run")
    def test_run_tests_success_mock(self, mock_sub):
        mock_sub.return_value = MagicMock(
            stdout="======================= 10 passed in 1.05s ========================",
            stderr="",
            returncode=0,
        )
        runner = TestRunner()
        res = runner.run_tests(target="tests/test_mock.py")

        assert res.success is True
        assert res.passed == 10
        mock_sub.assert_called_once()

    @patch("subprocess.run")
    def test_run_tests_timeout_handling(self, mock_sub):
        mock_sub.side_effect = subprocess.TimeoutExpired(cmd=["pytest"], timeout=5)
        runner = TestRunner()
        res = runner.run_tests(timeout=5)

        assert res.success is False
        assert "timed out" in res.output.lower()
        assert len(res.error_summary) == 1

    def test_test_result_to_dict(self):
        res = TestResult(
            success=True,
            passed=5,
            failed=0,
            skipped=1,
            total=6,
            duration_seconds=1.23,
            coverage_percent=95.0,
            output="test output",
        )
        data = res.to_dict()
        assert data["success"] is True
        assert data["passed"] == 5
        assert data["coverage_percent"] == 95.0


# ─────────────────────────────────────────────────────────────────────────────
# 3. PatchGenerator & PatchValidator Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPatchGeneratorAndValidator:

    def test_generate_diff(self):
        orig = "def foo():\n    return 1\n"
        mod = "def foo():\n    return 2\n"

        diff = PatchGenerator.generate_diff(orig, mod, filename="test.py")
        assert "--- a/test.py" in diff
        assert "+++ b/test.py" in diff
        assert "-    return 1" in diff
        assert "+    return 2" in diff

    def test_apply_patch_success(self):
        orig = "line 1\nline 2\nline 3"
        mod = "line 1\nline TWO\nline 3"
        diff = PatchGenerator.generate_diff(orig, mod, filename="f.py")

        ok, result, err = PatchGenerator.apply_patch(orig, diff)
        assert ok is True
        assert result == mod
        assert err is None

    def test_apply_patch_empty_diff(self):
        orig = "hello world"
        ok, result, err = PatchGenerator.apply_patch(orig, "")
        assert ok is True
        assert result == orig

    def test_apply_patch_invalid_diff(self):
        orig = "hello world"
        ok, result, err = PatchGenerator.apply_patch(orig, "Not a valid diff hunk")
        assert ok is False
        assert err is not None

    def test_validate_patch_valid(self, tmp_path):
        f = tmp_path / "valid.py"
        f.write_text("x = 1\n", encoding="utf-8")

        validator = PatchValidator()
        res = validator.validate_patch(f, "x = 2\ny = 3\n")
        assert res.is_valid is True
        assert res.errors == []
        assert res.added_lines >= 1

    def test_validate_patch_syntax_error(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def ok():\n    pass\n", encoding="utf-8")

        validator = PatchValidator()
        res = validator.validate_patch(f, "def broken(\n    missing closing paren\n")
        assert res.is_valid is False
        assert any("syntax error" in e.lower() for e in res.errors)

    def test_validate_patch_protected_system_path(self):
        validator = PatchValidator(protected_paths=["c:\\windows", "/etc"])
        res = validator.validate_patch("c:\\windows\\system32\\config.py", "malicious = True\n")
        assert res.is_valid is False
        assert any("protected" in e.lower() for e in res.errors)

    def test_validate_patch_dangerous_pattern(self, tmp_path):
        f = tmp_path / "script.py"
        f.write_text("# script\n", encoding="utf-8")

        validator = PatchValidator()
        res = validator.validate_patch(f, "import os\nos.system('rm -rf /')\n")
        assert res.is_valid is False
        assert any("root deletion" in e.lower() for e in res.errors)


# ─────────────────────────────────────────────────────────────────────────────
# 4. PluginScaffolder Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPluginScaffolder:

    def test_scaffold_creates_complete_structure(self, tmp_path):
        scaffolder = PluginScaffolder(plugins_root=tmp_path)
        cfg = PluginScaffoldConfig(
            plugin_id="demo_widget",
            name="Demo Widget",
            version="1.0.0",
            description="A test widget for Neron.",
            tool_name="widget.display",
            permissions=["filesystem.read", "computer.screen"],
        )
        created = scaffolder.create_plugin_scaffold(cfg)

        assert created["directory"].is_dir()
        assert created["manifest"].is_file()
        assert created["plugin"].is_file()
        assert created["init"].is_file()
        assert created["test"].is_file()
        assert created["readme"].is_file()

        # Check manifest validity via PluginManifestValidator
        meta = PluginManifestValidator.load_manifest(created["directory"])
        assert meta.id == "demo_widget"
        assert meta.name == "Demo Widget"
        assert meta.version == "1.0.0"
        assert "widget.display" in meta.tools
        assert "computer.screen" in meta.permissions

    def test_scaffold_loads_and_executes_in_runtime(self, tmp_path):
        scaffolder = PluginScaffolder(plugins_root=tmp_path)
        cfg = PluginScaffoldConfig(
            plugin_id="runtime_tool",
            name="Runtime Tool",
            description="Verifies runtime loading of scaffolded plugin.",
            tool_name="runtime.execute",
        )
        created = scaffolder.create_plugin_scaffold(cfg)

        # Load plugin using Stage 10 PluginLoader
        meta = PluginManifestValidator.load_manifest(created["directory"])
        plugin = PluginLoader.load_plugin_from_metadata(meta)

        assert plugin.on_load() is True
        assert plugin.tool.name == "runtime.execute"
        result = plugin.tool.execute({"arg": "val"})
        assert result.success is True
        assert result.output["plugin"] == "runtime_tool"

        plugin.on_unload()

    def test_invalid_plugin_id_raises_value_error(self):
        scaffolder = PluginScaffolder()
        cfg = PluginScaffoldConfig(plugin_id="Invalid ID! With Spaces", name="Test")
        with pytest.raises(ValueError, match="Invalid plugin_id"):
            scaffolder.create_plugin_scaffold(cfg)


# ─────────────────────────────────────────────────────────────────────────────
# 5. DeveloperAgent Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDeveloperAgent:

    def test_agent_introspect_and_validate(self):
        agent = DeveloperAgent()

        # Introspect source
        info = agent.introspect_source("neron.security.permissions")
        assert info["is_valid_syntax"] is True
        assert len(info["classes"]) >= 2

        # Validate code
        valid_res = agent.validate_code("def add(x, y):\n    return x + y\n")
        assert valid_res["is_valid"] is True

        invalid_res = agent.validate_code("def syntax_err(:")
        assert invalid_res["is_valid"] is False
        assert invalid_res["error"] is not None

    def test_agent_diagnose_failure_hints(self):
        agent = DeveloperAgent()

        mod_hint = agent.diagnose_failure("ModuleNotFoundError: No module named 'foobar'")
        assert any("pip install" in h for h in mod_hint["hints"])

        syn_hint = agent.diagnose_failure("SyntaxError: invalid syntax at line 10")
        assert any("syntax" in h.lower() for h in syn_hint["hints"])

        perm_hint = agent.diagnose_failure("PermissionDeniedError: Capability 'filesystem.delete' rejected")
        assert any("permission" in h.lower() for h in perm_hint["hints"])

        timeout_hint = agent.diagnose_failure("subprocess.TimeoutExpired: command timed out")
        assert any("timeout" in h.lower() for h in timeout_hint["hints"])

    def test_agent_scaffold_plugin_wrapper(self, tmp_path):
        agent = DeveloperAgent(root_dir=tmp_path)
        out = agent.scaffold_plugin(
            plugin_id="agent_plugin",
            name="Agent Plugin",
            description="Created via agent.",
            output_dir=tmp_path / "custom_out",
        )
        assert out["status"] == "success"
        assert Path(out["paths"]["manifest"]).is_file()


# ─────────────────────────────────────────────────────────────────────────────
# 6. Developer Tools Registration & Execution Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDeveloperTools:

    def test_tools_registered_in_default_registry(self):
        registry = create_default_registry()
        assert registry.has("dev.inspect_source")
        assert registry.has("dev.run_tests")
        assert registry.has("dev.validate_code")
        assert registry.has("dev.create_plugin")

    def test_dev_inspect_source_tool_execution(self):
        tool = DevInspectSourceTool()

        # Test module inspection
        res = tool.execute(target="neron.security.permissions")
        assert res.success is True
        assert res.output["is_valid_syntax"] is True

        # Test symbol search
        res_sym = tool.execute(target="dummy", symbol="Capability")
        assert res_sym.success is True
        assert res_sym.output["count"] >= 1

        # Test missing target
        res_err = tool.execute(target="")
        assert res_err.success is False

    def test_dev_validate_code_tool_execution(self):
        tool = DevValidateCodeTool()

        res_ok = tool.execute(code="a = 10\nb = 20\n")
        assert res_ok.success is True
        assert res_ok.output["is_valid"] is True

        res_bad = tool.execute(code="a = = 10")
        assert res_bad.success is False
        assert res_bad.output["is_valid"] is False

    @patch("neron.developer.test_runner.TestRunner.run_tests")
    def test_dev_run_tests_tool_execution(self, mock_run):
        mock_run.return_value = TestResult(
            success=True,
            passed=20,
            failed=0,
            skipped=0,
            duration_seconds=2.5,
        )
        tool = DevRunTestsTool()
        res = tool.execute(target="tests/test_developer.py")

        assert res.success is True
        assert res.output["passed"] == 20

    def test_dev_create_plugin_tool_execution(self, tmp_path):
        scaffolder = PluginScaffolder(plugins_root=tmp_path)
        tool = DevCreatePluginScaffoldTool(scaffolder=scaffolder)

        res = tool.execute(
            plugin_id="my_cli_tool",
            name="My CLI Tool",
            description="Custom CLI tool",
            tool_name="mycli.execute",
        )
        assert res.success is True
        assert res.output["plugin_id"] == "my_cli_tool"
        assert (tmp_path / "my_cli_tool" / "plugin.yaml").is_file()


# ─────────────────────────────────────────────────────────────────────────────
# 7. DAGPlanner Developer Intents Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDAGPlannerDeveloperIntents:

    def test_run_tests_goal(self):
        planner = DAGPlanner()
        plan = planner.plan(goal="run unit tests", context={}, available_tools=[])
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "dev.run_tests"

    def test_run_tests_with_target_goal(self):
        planner = DAGPlanner()
        plan = planner.plan(goal="run tests for tests/test_developer.py", context={}, available_tools=[])
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "dev.run_tests"
        assert plan.steps[0].arguments.get("target") == "tests/test_developer.py"

    def test_inspect_module_goal(self):
        planner = DAGPlanner()
        plan = planner.plan(goal="inspect module neron.developer.introspector", context={}, available_tools=[])
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "dev.inspect_source"
        assert plan.steps[0].arguments.get("target") == "neron.developer.introspector"

    def test_scaffold_plugin_goal(self):
        planner = DAGPlanner()
        plan = planner.plan(goal="create plugin weather-reporter", context={}, available_tools=[])
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "dev.create_plugin"
        assert plan.steps[0].arguments.get("plugin_id") == "weather-reporter"
