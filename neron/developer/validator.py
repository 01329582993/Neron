"""Pre-deployment validation gate verifying syntax, security guardrails, and test suites."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from neron.developer.introspector import CodeIntrospector
from neron.developer.patcher import PatchValidator
from neron.developer.staging import StagingWorkspace
from neron.developer.test_runner import TestResult, TestRunner
from neron.utils.logger import get_logger

logger = get_logger("developer.validator")


@dataclass
class ValidationReport:
    """Pre-deployment verification report across syntax, safety, and testing."""
    is_valid: bool
    staged_files: List[str] = field(default_factory=list)
    syntax_errors: Dict[str, str] = field(default_factory=dict)
    security_violations: Dict[str, str] = field(default_factory=dict)
    test_result: Optional[TestResult] = None
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "staged_files": self.staged_files,
            "syntax_errors": self.syntax_errors,
            "security_violations": self.security_violations,
            "test_result": self.test_result.to_dict() if self.test_result else None,
            "summary": self.summary,
        }


class ValidationGate:
    """
    Enforces a strict pre-deployment gate before any staged modification
    can be written to the production workspace.
    """

    def __init__(
        self,
        introspector: Optional[CodeIntrospector] = None,
        patch_validator: Optional[PatchValidator] = None,
        test_runner: Optional[TestRunner] = None,
    ):
        self.introspector = introspector or CodeIntrospector()
        self.patch_validator = patch_validator or PatchValidator()
        self.test_runner = test_runner or TestRunner()

    def validate_staging(
        self,
        staging: StagingWorkspace,
        run_tests: bool = True,
        test_target: Optional[str] = None,
    ) -> ValidationReport:
        """
        Validate all staged files:
        1. Check Python syntax via AST
        2. Check protected paths and dangerous patterns
        3. Execute test suite if syntax & security checks pass
        """
        staged_files = staging.get_staged_files()
        syntax_errors: Dict[str, str] = {}
        security_violations: Dict[str, str] = {}

        if not staged_files:
            return ValidationReport(
                is_valid=False,
                summary="Validation failed: No files are currently staged.",
            )

        # 1. Syntax & security check per staged file
        for rel_file in staged_files:
            content = staging.read_staged_file(rel_file) or ""

            # Check Python syntax
            if rel_file.endswith(".py"):
                is_valid_syn, err, line = self.introspector.validate_syntax(content)
                if not is_valid_syn:
                    syntax_errors[rel_file] = f"Line {line}: {err}"

            # Check security / dangerous patterns
            target_prod_file = staging.production_root / rel_file
            patch_res = self.patch_validator.validate_patch(target_prod_file, content)
            if not patch_res.is_valid:
                security_violations[rel_file] = "; ".join(patch_res.errors)

        # If static checks fail, reject immediately
        if syntax_errors or security_violations:
            err_parts = []
            if syntax_errors:
                err_parts.append(f"{len(syntax_errors)} syntax error(s)")
            if security_violations:
                err_parts.append(f"{len(security_violations)} security violation(s)")
            return ValidationReport(
                is_valid=False,
                staged_files=staged_files,
                syntax_errors=syntax_errors,
                security_violations=security_violations,
                summary=f"Validation failed with {', '.join(err_parts)}.",
            )

        # 2. Dynamic test suite execution
        test_res: Optional[TestResult] = None
        if run_tests:
            logger.info("Running pre-deployment test suite verification...")
            test_res = self.test_runner.run_tests(target=test_target)
            if not test_res.success:
                return ValidationReport(
                    is_valid=False,
                    staged_files=staged_files,
                    syntax_errors=syntax_errors,
                    security_violations=security_violations,
                    test_result=test_res,
                    summary=f"Pre-deployment test suite failed: {test_res.failed} failures, {test_res.errors} errors.",
                )

        summary_msg = f"All {len(staged_files)} staged file(s) passed pre-deployment validation."
        if test_res:
            summary_msg += f" Test suite passed ({test_res.passed} passed in {test_res.duration_seconds}s)."

        return ValidationReport(
            is_valid=True,
            staged_files=staged_files,
            syntax_errors={},
            security_violations={},
            test_result=test_res,
            summary=summary_msg,
        )
