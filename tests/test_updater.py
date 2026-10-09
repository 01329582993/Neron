"""Exhaustive tests for Stage 14: Sandboxed Self-Update Pipeline, Staging, Backup, Validation, and Rollback."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from neron.core.planner.dag_planner import DAGPlanner
from neron.developer import (
    BackupManager,
    DeploymentReport,
    SelfUpdatePipeline,
    StagingWorkspace,
    TestResult,
    ValidationGate,
    ValidationReport,
)
from neron.diagnostics.health import STATUS_FAILED, STATUS_HEALTHY
from neron.tools import create_default_registry
from neron.tools.developer.tools import (
    DevDeployStagedTool,
    DevRollbackTool,
    DevStagePatchTool,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. StagingWorkspace Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestStagingWorkspace:

    def test_staging_workspace_init_and_stage(self, tmp_path):
        prod_root = tmp_path / "prod"
        prod_root.mkdir()
        staging_dir = tmp_path / "staging"

        staging = StagingWorkspace(base_dir=staging_dir, production_root=prod_root)
        dest = staging.stage_file("neron/utils/sample.py", "x = 42\n")

        assert dest.is_file()
        assert dest.read_text(encoding="utf-8") == "x = 42\n"
        assert staging.get_staged_files() == ["neron/utils/sample.py"]

    def test_read_staged_file(self, tmp_path):
        staging = StagingWorkspace(base_dir=tmp_path / "staging")
        staging.stage_file("foo/bar.txt", "Hello Neron")

        assert staging.read_staged_file("foo/bar.txt") == "Hello Neron"
        assert staging.read_staged_file("nonexistent.txt") is None

    def test_get_diff_summary(self, tmp_path):
        prod_root = tmp_path / "prod"
        prod_root.mkdir()
        orig_file = prod_root / "test.py"
        orig_file.write_text("def hello():\n    return 1\n", encoding="utf-8")

        staging = StagingWorkspace(base_dir=tmp_path / "staging", production_root=prod_root)
        staging.stage_file("test.py", "def hello():\n    return 2\n")

        diffs = staging.get_diff_summary()
        assert "test.py" in diffs
        assert "-    return 1" in diffs["test.py"]
        assert "+    return 2" in diffs["test.py"]

    def test_clear_and_prepare(self, tmp_path):
        staging = StagingWorkspace(base_dir=tmp_path / "staging")
        staging.stage_file("a.txt", "A")
        assert len(staging.get_staged_files()) == 1

        staging.clear()
        assert staging.get_staged_files() == []

        staging.stage_file("b.txt", "B")
        staging.prepare()
        assert staging.get_staged_files() == []


# ─────────────────────────────────────────────────────────────────────────────
# 2. BackupManager Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBackupManager:

    def test_create_and_restore_backup(self, tmp_path):
        prod_root = tmp_path / "prod"
        prod_root.mkdir()
        file1 = prod_root / "config.txt"
        file1.write_text("original config", encoding="utf-8")

        backup_root = tmp_path / "backups"
        mgr = BackupManager(backup_root=backup_root, production_root=prod_root)

        # 1. Create backup
        backup_id = mgr.create_backup(["config.txt"], description="Pre-update")
        assert backup_id.startswith("backup_")
        assert (backup_root / backup_id / "backup_meta.json").is_file()
        assert (backup_root / backup_id / "config.txt").is_file()

        # 2. Overwrite file in production
        file1.write_text("corrupted config", encoding="utf-8")
        assert file1.read_text(encoding="utf-8") == "corrupted config"

        # 3. Restore backup
        ok = mgr.restore_backup(backup_id)
        assert ok is True
        assert file1.read_text(encoding="utf-8") == "original config"

    def test_list_backups_and_latest(self, tmp_path):
        prod_root = tmp_path / "prod"
        prod_root.mkdir()
        mgr = BackupManager(backup_root=tmp_path / "backups", production_root=prod_root)

        b1 = mgr.create_backup([])
        b2 = mgr.create_backup([])

        backups = mgr.list_backups()
        assert len(backups) == 2
        assert mgr.get_latest_backup_id() == b2

    def test_restore_nonexistent_backup_raises_error(self, tmp_path):
        mgr = BackupManager(backup_root=tmp_path / "backups", production_root=tmp_path / "prod")
        with pytest.raises(FileNotFoundError):
            mgr.restore_backup("backup_nonexistent_123")

    def test_restore_when_no_backups_returns_false(self, tmp_path):
        mgr = BackupManager(backup_root=tmp_path / "backups", production_root=tmp_path / "prod")
        assert mgr.restore_backup(None) is False


# ─────────────────────────────────────────────────────────────────────────────
# 3. ValidationGate Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestValidationGate:

    def test_validate_empty_staging_fails(self, tmp_path):
        staging = StagingWorkspace(base_dir=tmp_path / "staging")
        gate = ValidationGate()

        report = gate.validate_staging(staging)
        assert report.is_valid is False
        assert "No files are currently staged" in report.summary

    def test_validate_syntax_error_fails(self, tmp_path):
        staging = StagingWorkspace(base_dir=tmp_path / "staging", production_root=tmp_path / "prod")
        staging.stage_file("broken.py", "def broken(\n    return 42\n")

        gate = ValidationGate()
        report = gate.validate_staging(staging, run_tests=False)

        assert report.is_valid is False
        assert "broken.py" in report.syntax_errors
        assert "syntax error" in report.summary.lower()

    def test_validate_security_violation_fails(self, tmp_path):
        prod_root = tmp_path / "prod"
        prod_root.mkdir()
        staging = StagingWorkspace(base_dir=tmp_path / "staging", production_root=prod_root)
        staging.stage_file("danger.py", "import os\nos.system('rm -rf /')\n")

        gate = ValidationGate()
        report = gate.validate_staging(staging, run_tests=False)

        assert report.is_valid is False
        assert "danger.py" in report.security_violations
        assert "security violation" in report.summary.lower()

    @patch("neron.developer.test_runner.TestRunner.run_tests")
    def test_validate_test_suite_failure(self, mock_tests, tmp_path):
        mock_tests.return_value = TestResult(
            success=False,
            passed=5,
            failed=2,
            errors=0,
            duration_seconds=1.5,
            error_summary=["FAILED test_a.py"],
        )
        prod_root = tmp_path / "prod"
        prod_root.mkdir()
        staging = StagingWorkspace(base_dir=tmp_path / "staging", production_root=prod_root)
        staging.stage_file("good.py", "x = 10\n")

        gate = ValidationGate()
        report = gate.validate_staging(staging, run_tests=True)

        assert report.is_valid is False
        assert report.test_result is not None
        assert report.test_result.failed == 2

    @patch("neron.developer.test_runner.TestRunner.run_tests")
    def test_validate_success(self, mock_tests, tmp_path):
        mock_tests.return_value = TestResult(
            success=True,
            passed=25,
            duration_seconds=0.8,
        )
        prod_root = tmp_path / "prod"
        prod_root.mkdir()
        staging = StagingWorkspace(base_dir=tmp_path / "staging", production_root=prod_root)
        staging.stage_file("feature.py", "def calculate():\n    return 100\n")

        gate = ValidationGate()
        report = gate.validate_staging(staging, run_tests=True)

        assert report.is_valid is True
        assert "passed" in report.summary.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 4. SelfUpdatePipeline Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSelfUpdatePipeline:

    def test_stage_update_summary(self, tmp_path):
        prod_root = tmp_path / "prod"
        prod_root.mkdir()
        pipeline = SelfUpdatePipeline(production_root=prod_root)

        res = pipeline.stage_update({"mod.py": "x = 1\n", "doc.txt": "Notes\n"})
        assert res["staged_count"] == 2
        assert "mod.py" in res["staged_files"]
        assert "doc.txt" in res["staged_files"]

    def test_deploy_atomic_successful(self, tmp_path):
        prod_root = tmp_path / "prod"
        prod_root.mkdir()
        orig_file = prod_root / "app.py"
        orig_file.write_text("version = 1\n", encoding="utf-8")

        pipeline = SelfUpdatePipeline(production_root=prod_root)
        pipeline.stage_update({"app.py": "version = 2\n"})

        report = pipeline.deploy_atomic(require_health_check=False, skip_tests=True)
        assert report.success is True
        assert report.rolled_back is False
        assert orig_file.read_text(encoding="utf-8") == "version = 2\n"
        assert report.backup_id is not None

        # Staging workspace should be cleared
        assert pipeline.staging.get_staged_files() == []

    def test_deploy_aborted_when_syntax_invalid(self, tmp_path):
        prod_root = tmp_path / "prod"
        prod_root.mkdir()
        orig_file = prod_root / "stable.py"
        orig_file.write_text("x = 100\n", encoding="utf-8")

        pipeline = SelfUpdatePipeline(production_root=prod_root)
        pipeline.stage_update({"stable.py": "def broken(\n"})

        report = pipeline.deploy_atomic(require_health_check=False, skip_tests=True)
        assert report.success is False
        # File should remain unchanged in production
        assert orig_file.read_text(encoding="utf-8") == "x = 100\n"

    def test_deploy_auto_rollback_on_health_check_failure(self, tmp_path):
        prod_root = tmp_path / "prod"
        prod_root.mkdir()
        orig_file = prod_root / "core.py"
        orig_file.write_text("healthy_core = True\n", encoding="utf-8")

        pipeline = SelfUpdatePipeline(production_root=prod_root)
        pipeline.stage_update({"core.py": "healthy_core = False\n"})

        # Mock HealthManager to simulate failing health check
        mock_health = MagicMock()
        mock_health.run_full_diagnostics.return_value = []
        mock_health.overall_status.return_value = STATUS_FAILED
        pipeline.health_mgr = mock_health

        report = pipeline.deploy_atomic(require_health_check=True, auto_rollback=True, skip_tests=True)

        assert report.success is False
        assert report.rolled_back is True
        assert "rolled back" in report.message.lower()

        # Target file must be restored to original content!
        assert orig_file.read_text(encoding="utf-8") == "healthy_core = True\n"

    def test_manual_rollback(self, tmp_path):
        prod_root = tmp_path / "prod"
        prod_root.mkdir()
        target = prod_root / "val.txt"
        target.write_text("old value", encoding="utf-8")

        pipeline = SelfUpdatePipeline(production_root=prod_root)
        pipeline.stage_update({"val.txt": "new value"})
        pipeline.deploy_atomic(require_health_check=False, skip_tests=True)
        assert target.read_text(encoding="utf-8") == "new value"

        # Trigger manual rollback
        rb_res = pipeline.rollback()
        assert rb_res["success"] is True
        assert target.read_text(encoding="utf-8") == "old value"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Developer Self-Update Tools Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestStage14Tools:

    def test_stage14_tools_registered_in_default_registry(self):
        registry = create_default_registry()
        assert registry.has("dev.stage_patch")
        assert registry.has("dev.deploy_staged")
        assert registry.has("dev.rollback")

    def test_dev_stage_patch_tool_execution(self, tmp_path):
        staging = StagingWorkspace(base_dir=tmp_path / "staging")
        tool = DevStagePatchTool(staging=staging)

        res = tool.execute(file_path="foo/test.py", content="x = 10\n")
        assert res.success is True
        assert res.output["staged_file"] == "foo/test.py"
        assert (tmp_path / "staging" / "workspace" / "foo" / "test.py").is_file()

    def test_dev_deploy_staged_tool_execution(self, tmp_path):
        prod_root = tmp_path / "prod"
        prod_root.mkdir()
        f = prod_root / "sample.py"
        f.write_text("v = 1\n", encoding="utf-8")

        pipeline = SelfUpdatePipeline(production_root=prod_root)
        pipeline.stage_update({"sample.py": "v = 2\n"})

        tool = DevDeployStagedTool(pipeline=pipeline)
        res = tool.execute(skip_tests=True, auto_rollback=True)

        assert res.success is True
        assert res.output["success"] is True
        assert f.read_text(encoding="utf-8") == "v = 2\n"

    def test_dev_rollback_tool_execution(self, tmp_path):
        prod_root = tmp_path / "prod"
        prod_root.mkdir()
        f = prod_root / "config.ini"
        f.write_text("initial=true\n", encoding="utf-8")

        pipeline = SelfUpdatePipeline(production_root=prod_root)
        pipeline.stage_update({"config.ini": "initial=false\n"})
        pipeline.deploy_atomic(require_health_check=False, skip_tests=True)

        tool = DevRollbackTool(pipeline=pipeline)
        res = tool.execute()

        assert res.success is True
        assert f.read_text(encoding="utf-8") == "initial=true\n"


# ─────────────────────────────────────────────────────────────────────────────
# 6. DAGPlanner Self-Update Intents Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDAGPlannerSelfUpdateIntents:

    def test_deploy_staged_intent(self):
        planner = DAGPlanner()
        plan = planner.plan(goal="deploy staged update", context={}, available_tools=[])
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "dev.deploy_staged"

    def test_rollback_update_intent(self):
        planner = DAGPlanner()
        plan = planner.plan(goal="rollback update", context={}, available_tools=[])
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "dev.rollback"

    def test_rollback_to_checkpoint_intent(self):
        planner = DAGPlanner()
        plan = planner.plan(goal="rollback to checkpoint backup_20261009_001", context={}, available_tools=[])
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "dev.rollback"
        assert plan.steps[0].arguments.get("backup_id") == "backup_20261009_001"
