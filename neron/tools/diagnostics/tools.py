"""Diagnostic tools exposed through the Neron tool registry — Stage 12."""

from __future__ import annotations

from typing import Any, Dict, List

from neron.diagnostics.health import HealthManager
from neron.tools.base import BaseTool, ToolResult


class DiagnosticsRunTool(BaseTool):
    """
    Run a full self-diagnostic sweep and return structured results.

    Returns a summary table of every subsystem check including status,
    details, and any remediation hints. Useful for agents that want to
    auto-detect problems before taking actions.
    """

    @property
    def name(self) -> str:
        return "diagnostics.run"

    @property
    def description(self) -> str:
        return (
            "Run a complete system self-diagnostic check covering Python runtime, "
            "dependencies, OS controller, storage, hardware, Ollama endpoint, "
            "network latency, and audio subsystem. Returns structured results."
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "verbose": {
                    "type": "boolean",
                    "description": "If true, include remediation hints in the output.",
                    "default": True,
                }
            },
            "required": [],
        }

    @property
    def required_capabilities(self) -> List[str]:
        return ["READ"]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        verbose = arguments.get("verbose", True)
        try:
            manager = HealthManager()
            results = manager.run_full_diagnostics()
            overall = manager.overall_status(results)

            rows = []
            for r in results:
                row: Dict[str, Any] = {
                    "name": r.name,
                    "status": r.status,
                    "details": r.details,
                }
                if verbose and r.remediation_hint:
                    row["remediation_hint"] = r.remediation_hint
                rows.append(row)

            summary_lines = [f"[{r.status:8s}] {r.name}" for r in results]
            summary_text = "\n".join(summary_lines)

            return ToolResult(
                success=True,
                output=f"Overall: {overall}\n\n{summary_text}",
                metadata={
                    "overall_status": overall,
                    "checks": rows,
                    "check_count": len(results),
                    "failed": sum(1 for r in results if r.status == "FAILED"),
                    "warnings": sum(1 for r in results if r.status in ("WARNING", "DEGRADED")),
                },
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Diagnostics failed: {e}")


class DiagnosticsHardwareTool(BaseTool):
    """
    Evaluate hardware capabilities and return a capability tier.

    Reports CPU core count, RAM size, GPU availability, and classifies the
    system as MINIMAL / STANDARD / PERFORMANCE / HIGH_END. Used by agents
    to auto-select appropriate model sizes and feature flags.
    """

    @property
    def name(self) -> str:
        return "diagnostics.hardware"

    @property
    def description(self) -> str:
        return (
            "Evaluate system hardware (CPU, RAM, GPU) and return a capability tier. "
            "Tiers: MINIMAL, STANDARD, PERFORMANCE, HIGH_END. "
            "Use this before recommending LLM models or resource-intensive tasks."
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    @property
    def required_capabilities(self) -> List[str]:
        return ["READ"]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        try:
            manager = HealthManager()
            hw = manager.evaluate_hardware()
            gpu_str = (
                f"{', '.join(hw.gpu_names)} (CUDA available)"
                if hw.gpu_available
                else "No GPU detected — CPU inference mode"
            )
            summary = (
                f"CPU: {hw.cpu_model} — {hw.cpu_cores}P/{hw.cpu_logical}L cores\n"
                f"RAM: {hw.ram_total_gb:.1f} GB total / {hw.ram_available_gb:.1f} GB available\n"
                f"GPU: {gpu_str}\n"
                f"Tier: {hw.tier}"
            )
            return ToolResult(
                success=True,
                output=summary,
                metadata=hw.to_dict(),
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Hardware evaluation failed: {e}")
