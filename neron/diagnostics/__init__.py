"""Diagnostics and health monitoring package — Stage 12."""

from neron.diagnostics.health import (
    HealthCheckResult,
    HardwareCapabilityReport,
    HealthManager,
    run_cli_diagnostics,
    STATUS_HEALTHY,
    STATUS_WARNING,
    STATUS_DEGRADED,
    STATUS_FAILED,
)

__all__ = [
    "HealthManager",
    "HealthCheckResult",
    "HardwareCapabilityReport",
    "run_cli_diagnostics",
    "STATUS_HEALTHY",
    "STATUS_WARNING",
    "STATUS_DEGRADED",
    "STATUS_FAILED",
]
