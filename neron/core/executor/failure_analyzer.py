"""Failure analysis engine — classifies step failures and recommends recovery strategies."""

import re
from neron.core.state.models import FailureAnalysis, StepFailureMode
from neron.utils.logger import get_logger

logger = get_logger("core.failure_analyzer")

# Keyword maps for failure classification
_PERMISSION_KEYWORDS = ("permission denied", "access denied", "permissiondenied", "not allowed", "unauthorized")
_TIMEOUT_KEYWORDS = ("timeout", "timed out", "time limit exceeded")
_NOT_FOUND_KEYWORDS = ("tool not found", "not found", "no such file", "notimplementederror")
# Use regex with word boundaries so 'Unexpected' doesn't match 'expected'
_VERIFICATION_RE = re.compile(r"\b(verification failed|assertion)\b")


def analyze_failure(error: str, tool_name: str, retry_count: int, max_retries: int) -> FailureAnalysis:
    """
    Classify why a step failed and recommend a recovery path.

    Args:
        error: The raw error string from the step execution.
        tool_name: The name of the tool that failed.
        retry_count: How many retries have already been attempted.
        max_retries: The maximum number of retries allowed.

    Returns:
        A FailureAnalysis with mode, retryability, and recovery suggestion.
    """
    lower = error.lower()

    # Emergency stop — non-retryable
    if "emergency stop" in lower or "emergencystoptriggered" in lower:
        return FailureAnalysis(
            mode=StepFailureMode.EMERGENCY_STOP,
            is_retryable=False,
            recovery_suggestion="Emergency stop was triggered. Resume by resetting the emergency stop via CTRL+ALT+N.",
            raw_error=error,
        )

    # Permission denied — non-retryable without user action
    if any(kw in lower for kw in _PERMISSION_KEYWORDS):
        return FailureAnalysis(
            mode=StepFailureMode.PERMISSION_DENIED,
            is_retryable=False,
            recovery_suggestion=(
                f"Tool '{tool_name}' was blocked by the permission engine. "
                "Switch to POWER_USER mode or grant explicit access to retry this action."
            ),
            raw_error=error,
        )

    # Tool not found — non-retryable
    if any(kw in lower for kw in _NOT_FOUND_KEYWORDS):
        return FailureAnalysis(
            mode=StepFailureMode.TOOL_NOT_FOUND,
            is_retryable=False,
            recovery_suggestion=(
                f"Tool '{tool_name}' was not found in the registry. "
                "Ensure the tool module is registered or install the required plugin."
            ),
            raw_error=error,
        )

    # Timeout — retryable once
    if any(kw in lower for kw in _TIMEOUT_KEYWORDS):
        return FailureAnalysis(
            mode=StepFailureMode.TIMEOUT,
            is_retryable=(retry_count < max_retries),
            recovery_suggestion=(
                f"Tool '{tool_name}' timed out. This may be transient. "
                "If it persists, increase the timeout configuration or check system load."
            ),
            raw_error=error,
        )

    # Verification failure — not worth retrying without plan change
    if _VERIFICATION_RE.search(lower):
        return FailureAnalysis(
            mode=StepFailureMode.VERIFICATION_FAILED,
            is_retryable=False,
            recovery_suggestion=(
                f"Post-step verification for '{tool_name}' failed — the action ran but the expected "
                "outcome was not observed. Manual inspection recommended."
            ),
            raw_error=error,
        )

    # Generic runtime error — retryable up to max_retries
    return FailureAnalysis(
        mode=StepFailureMode.TOOL_RUNTIME_ERROR,
        is_retryable=(retry_count < max_retries),
        recovery_suggestion=(
            f"Tool '{tool_name}' encountered a runtime error. "
            f"Attempt {retry_count + 1}/{max_retries + 1}. "
            "If retries are exhausted, inspect logs for root cause."
        ),
        raw_error=error,
    )
