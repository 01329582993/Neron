"""Self-update orchestration pipeline coordinating staging, validation, atomic deploy, and rollback."""

from dataclasses import dataclass, field
from pathlib import Path
import shutil
from typing import Any, Callable, Dict, List, Optional, Union

from neron.developer.backup import BackupManager
from neron.developer.staging import StagingWorkspace
from neron.developer.validator import ValidationGate, ValidationReport
from neron.diagnostics.health import HealthManager, STATUS_FAILED
from neron.utils.logger import get_logger

logger = get_logger("developer.updater")


@dataclass
class DeploymentReport:
    """Detailed summary of an atomic deployment execution."""
    success: bool
    deployed_files: List[str] = field(default_factory=list)
    backup_id: Optional[str] = None
    rolled_back: bool = False
    validation_report: Optional[ValidationReport] = None
    health_status: Optional[str] = None
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "deployed_files": self.deployed_files,
            "backup_id": self.backup_id,
            "rolled_back": self.rolled_back,
            "validation_report": self.validation_report.to_dict() if self.validation_report else None,
            "health_status": self.health_status,
            "message": self.message,
        }


class SelfUpdatePipeline:
    """
    Executes the Neron Development Loop:
    Staging -> Validation Gate -> User Approval -> Atomic Deploy -> Post-Health Check -> Auto-Rollback.
    """

    def __init__(
        self,
        production_root: Optional[Union[str, Path]] = None,
        staging: Optional[StagingWorkspace] = None,
        backup_manager: Optional[BackupManager] = None,
        validation_gate: Optional[ValidationGate] = None,
        health_manager: Optional[HealthManager] = None,
    ):
        self.production_root = Path(production_root).resolve() if production_root else Path.cwd().resolve()
        self.staging = staging or StagingWorkspace(production_root=self.production_root)
        self.backup_mgr = backup_manager or BackupManager(production_root=self.production_root)
        self.validator = validation_gate or ValidationGate()
        self.health_mgr = health_manager or HealthManager()

    def stage_update(self, files: Dict[str, str]) -> Dict[str, Any]:
        """
        Stage one or more files in the isolated workspace.

        Args:
            files: Dictionary mapping relative file path to file content.
        """
        staged_paths = []
        for rel_path, content in files.items():
            staged_path = self.staging.stage_file(rel_path, content)
            staged_paths.append(str(staged_path))

        diffs = self.staging.get_diff_summary()
        return {
            "staged_count": len(files),
            "staged_files": self.staging.get_staged_files(),
            "diffs": diffs,
        }

    def validate_staged(
        self,
        run_tests: bool = True,
        test_target: Optional[str] = None,
    ) -> ValidationReport:
        """Run pre-deployment validation gate against current staged files."""
        return self.validator.validate_staging(
            staging=self.staging,
            run_tests=run_tests,
            test_target=test_target,
        )

    def get_diff_summary(self) -> Dict[str, str]:
        """Get unified diffs for all currently staged files."""
        return self.staging.get_diff_summary()

    def deploy_atomic(
        self,
        require_health_check: bool = True,
        auto_rollback: bool = True,
        skip_tests: bool = False,
        test_target: Optional[str] = None,
    ) -> DeploymentReport:
        """
        Atomically deploy staged modifications into production.

        Enforces:
        1. Pre-deployment validation gate (syntax + test runner)
        2. Creation of backup snapshot of target production files
        3. Atomic copying of files into production tree
        4. Post-deployment runtime health check
        5. Automated instant rollback if health check detects failure
        """
        staged_files = self.staging.get_staged_files()
        if not staged_files:
            return DeploymentReport(
                success=False,
                message="Cannot deploy: No files are currently staged.",
            )

        # 1. Pre-deployment validation gate
        val_report = self.validate_staged(run_tests=not skip_tests, test_target=test_target)
        if not val_report.is_valid:
            return DeploymentReport(
                success=False,
                validation_report=val_report,
                message=f"Deployment aborted by pre-deployment validation gate: {val_report.summary}",
            )

        # 2. Create backup snapshot of current target files
        backup_id = self.backup_mgr.create_backup(
            rel_files=staged_files,
            description=f"Snapshot prior to deploying {len(staged_files)} file(s)",
        )

        # 3. Deploy files into production
        deployed = []
        try:
            for rel_str in staged_files:
                src_file = self.staging.workspace_dir / rel_str
                dest_file = self.production_root / rel_str
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest_file)
                deployed.append(rel_str)
        except Exception as e:
            logger.error(f"Error copying files during deployment: {e}")
            if auto_rollback:
                logger.info(f"Triggering automated rollback to {backup_id}...")
                self.backup_mgr.restore_backup(backup_id)
            return DeploymentReport(
                success=False,
                backup_id=backup_id,
                rolled_back=auto_rollback,
                message=f"Deployment failed during file copy: {e}",
            )

        # 4. Post-deployment health check
        health_status = "HEALTHY"
        if require_health_check:
            try:
                diag_results = self.health_mgr.run_full_diagnostics()
                health_status = self.health_mgr.overall_status(diag_results)
                if health_status == STATUS_FAILED and auto_rollback:
                    logger.warning("Post-deployment health check FAILED. Initiating instant rollback...")
                    self.backup_mgr.restore_backup(backup_id)
                    return DeploymentReport(
                        success=False,
                        deployed_files=deployed,
                        backup_id=backup_id,
                        rolled_back=True,
                        health_status=health_status,
                        validation_report=val_report,
                        message="Post-deployment health check failed. Rolled back to previous checkpoint.",
                    )
            except Exception as e:
                logger.warning(f"Health check execution error: {e}")

        # 5. Cleanup staging on success
        self.staging.clear()
        logger.info(f"Successfully deployed {len(deployed)} file(s). Backup saved as '{backup_id}'.")

        return DeploymentReport(
            success=True,
            deployed_files=deployed,
            backup_id=backup_id,
            rolled_back=False,
            validation_report=val_report,
            health_status=health_status,
            message=f"Successfully deployed {len(deployed)} file(s) with backup checkpoint '{backup_id}'.",
        )

    def rollback(self, backup_id: Optional[str] = None) -> Dict[str, Any]:
        """Restore previous backup snapshot."""
        target_id = backup_id or self.backup_mgr.get_latest_backup_id()
        if not target_id:
            return {
                "success": False,
                "message": "No backup checkpoint found to restore.",
            }

        try:
            ok = self.backup_mgr.restore_backup(target_id)
            return {
                "success": ok,
                "backup_id": target_id,
                "message": f"Successfully rolled back to checkpoint '{target_id}'." if ok else "Rollback failed.",
            }
        except Exception as e:
            return {
                "success": False,
                "backup_id": target_id,
                "message": f"Rollback failed with error: {e}",
            }
