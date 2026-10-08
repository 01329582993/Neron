"""Automated test execution and coverage evaluation engine for Neron."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Union

from neron.utils.logger import get_logger

logger = get_logger("developer.test_runner")


@dataclass
class TestResult:
    """Summary of a pytest test execution run."""
    __test__ = False

    success: bool
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    total: int = 0
    duration_seconds: float = 0.0
    coverage_percent: Optional[float] = None
    output: str = ""
    error_summary: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "total": self.total,
            "duration_seconds": self.duration_seconds,
            "coverage_percent": self.coverage_percent,
            "output_length": len(self.output),
            "error_summary": self.error_summary,
        }


class TestRunner:
    """
    Executes unit and integration test suites using pytest and parses results.
    """
    __test__ = False

    def __init__(self, root_dir: Optional[Union[str, Path]] = None):
        self.root_dir = Path(root_dir).resolve() if root_dir else Path.cwd().resolve()

    def parse_pytest_output(
        self,
        stdout: str,
        stderr: str = "",
        exit_code: int = 0,
    ) -> TestResult:
        """
        Parse raw pytest output string into a structured TestResult.
        """
        combined = (stdout + "\n" + stderr).strip()

        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        duration = 0.0
        coverage = None
        error_summary = []

        # Parse passed count: e.g. "12 passed", "126 passed"
        passed_match = re.search(r"(\d+)\s+passed", combined)
        if passed_match:
            passed = int(passed_match.group(1))

        # Parse failed count: e.g. "2 failed"
        failed_match = re.search(r"(\d+)\s+failed", combined)
        if failed_match:
            failed = int(failed_match.group(1))

        # Parse skipped count: e.g. "3 skipped"
        skipped_match = re.search(r"(\d+)\s+skipped", combined)
        if skipped_match:
            skipped = int(skipped_match.group(1))

        # Parse errors count: e.g. "1 error" or "2 errors"
        errors_match = re.search(r"(\d+)\s+error", combined)
        if errors_match:
            errors = int(errors_match.group(1))

        # Parse duration: e.g. "in 72.22s" or "in 0.45s (0:00:00)"
        dur_match = re.search(r"in\s+(\d+\.?\d*)s", combined)
        if dur_match:
            try:
                duration = float(dur_match.group(1))
            except ValueError:
                duration = 0.0

        # Parse coverage percentage: e.g. "TOTAL ... 85%"
        cov_match = re.search(r"TOTAL\s+.*?(\d+)%", combined)
        if cov_match:
            try:
                coverage = float(cov_match.group(1))
            except ValueError:
                coverage = None

        # Extract failed test names / FAILED lines
        for line in combined.splitlines():
            line_str = line.strip()
            if line_str.startswith("FAILED ") or line_str.startswith("ERROR "):
                error_summary.append(line_str)

        total = passed + failed + skipped + errors
        # If exit_code is 0, it succeeded. If tests were run, failed/errors must be 0
        success = (exit_code == 0) and (failed == 0) and (errors == 0)

        return TestResult(
            success=success,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            total=total,
            duration_seconds=duration,
            coverage_percent=coverage,
            output=combined,
            error_summary=error_summary,
        )

    def run_tests(
        self,
        target: Optional[str] = None,
        timeout: int = 120,
        with_coverage: bool = False,
        extra_args: Optional[List[str]] = None,
    ) -> TestResult:
        """
        Execute pytest in a subprocess and return structured TestResult.
        """
        cmd = [sys.executable, "-m", "pytest"]

        if target:
            target_path = Path(target)
            if not target_path.is_absolute():
                target_path = self.root_dir / target
            cmd.append(str(target_path))

        if with_coverage:
            cmd.extend(["--cov=neron", "--cov-report=term"])

        if extra_args:
            cmd.extend(extra_args)

        logger.info(f"Running test suite: {' '.join(cmd)}")
        start_time = time.monotonic()

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = time.monotonic() - start_time
            result = self.parse_pytest_output(proc.stdout, proc.stderr, proc.returncode)
            if result.duration_seconds == 0.0:
                result.duration_seconds = round(elapsed, 2)
            return result

        except subprocess.TimeoutExpired as e:
            elapsed = time.monotonic() - start_time
            out = ""
            if e.stdout:
                out += e.stdout if isinstance(e.stdout, str) else e.stdout.decode("utf-8", errors="replace")
            return TestResult(
                success=False,
                duration_seconds=round(elapsed, 2),
                output=f"Test execution timed out after {timeout} seconds.\n{out}",
                error_summary=[f"TimeoutExpired: Tests exceeded {timeout}s limit"],
            )
        except Exception as e:
            elapsed = time.monotonic() - start_time
            return TestResult(
                success=False,
                duration_seconds=round(elapsed, 2),
                output=f"Failed to execute pytest: {e}",
                error_summary=[str(e)],
            )
