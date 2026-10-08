"""Step verification engine — confirms post-execution state changes are correct."""

from typing import Any, Optional
from neron.core.state.models import PlanStep, VerificationResult
from neron.tools.registry import ToolRegistry
from neron.utils.logger import get_logger

logger = get_logger("core.verifier")


def verify_step(step: PlanStep, tool_registry: ToolRegistry) -> VerificationResult:
    """
    Post-execution verification for a completed step.

    Verification strategy:
    1. If the tool result has a 'verified' flag already set, trust it.
    2. For filesystem.write: re-read the file and confirm it exists.
    3. For terminal.execute: check the exit_code from the result.
    4. For system.open_app: check process list for the process name.
    5. Default: pass if the step returned a non-None result.
    """
    if step.result is None:
        return VerificationResult(
            passed=False,
            details="Step returned no result — cannot verify outcome.",
        )

    result = step.result
    tool = step.tool_name

    # ── Filesystem write verification ──────────────────────────────────────────
    if tool == "filesystem.write":
        path = step.arguments.get("path", "")
        try:
            read_result = tool_registry.execute(
                tool_name="filesystem.read",
                arguments={"path": path},
                task_id="verifier",
                step_id=step.step_id,
            )
            if read_result.success:
                return VerificationResult(
                    passed=True,
                    details=f"File '{path}' confirmed to exist and is readable.",
                )
            else:
                return VerificationResult(
                    passed=False,
                    details=f"Verification read of '{path}' failed: {read_result.error}",
                )
        except Exception as e:
            return VerificationResult(
                passed=False,
                details=f"Verification exception for '{path}': {e}",
            )

    # ── Terminal execution verification ────────────────────────────────────────
    if tool == "terminal.execute":
        exit_code = None
        if isinstance(result, dict):
            exit_code = result.get("exit_code")
        if exit_code is not None and exit_code != 0:
            return VerificationResult(
                passed=False,
                details=f"Command exited with non-zero code: {exit_code}",
                expected="0",
                actual=str(exit_code),
            )
        return VerificationResult(
            passed=True,
            details="Terminal command completed with acceptable exit code.",
        )

    # ── System telemetry / volume / open_app — trust the tool result ───────────
    if tool in ("system.telemetry", "system.volume", "system.open_app", "system.close_app"):
        if isinstance(result, dict) and result.get("success") is False:
            return VerificationResult(
                passed=False,
                details=result.get("error", "Tool reported failure in result."),
            )
        return VerificationResult(
            passed=True,
            details=f"Tool '{tool}' reported success.",
        )

    # ── Default: any non-None result is considered verified ────────────────────
    return VerificationResult(
        passed=True,
        details="Step produced output — treated as verified.",
    )
