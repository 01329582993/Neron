"""Neron Desktop Console — rich terminal UI for the active agent session."""

from __future__ import annotations

import sys
import time
import threading
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.text import Text
    from rich.align import Align
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from neron.core.state.models import TaskPlan, TaskState, PlanStep
from neron.utils.logger import get_logger

if TYPE_CHECKING:
    from neron.core.agent.base import NeronAgent

logger = get_logger("ui.console")


# ─────────────────────────────────────────────────────────────────────────────
# Console color palette
# ─────────────────────────────────────────────────────────────────────────────

STATE_STYLES = {
    TaskState.PENDING:               ("⏳", "dim white"),
    TaskState.PLANNING:              ("🧠", "cyan"),
    TaskState.WAITING_FOR_PERMISSION:("🔐", "yellow"),
    TaskState.EXECUTING:             ("⚡", "bright_cyan bold"),
    TaskState.VERIFYING:             ("🔍", "blue"),
    TaskState.COMPLETED:             ("✅", "bright_green"),
    TaskState.FAILED:                ("❌", "bright_red"),
    TaskState.CANCELLED:             ("🚫", "dim red"),
    TaskState.SKIPPED:               ("⏭️",  "dim yellow"),
}


def _state_label(state: TaskState) -> str:
    icon, style = STATE_STYLES.get(state, ("?", "white"))
    return f"[{style}]{icon} {state.value}[/{style}]"


# ─────────────────────────────────────────────────────────────────────────────
# Plan Summary Panel
# ─────────────────────────────────────────────────────────────────────────────

def _build_plan_table(plans: List[TaskPlan]) -> Table:
    """Build a rich Table summarising recent task plans."""
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold bright_cyan",
        border_style="bright_black",
        expand=True,
    )
    table.add_column("ID", width=14, style="dim")
    table.add_column("Goal", ratio=3)
    table.add_column("Steps", width=7, justify="center")
    table.add_column("Status", width=22)
    table.add_column("Duration", width=12, justify="right")

    for plan in plans[-8:]:   # most recent 8
        icon, style = STATE_STYLES.get(plan.state, ("?", "white"))
        status_text = f"[{style}]{icon} {plan.state.value}[/{style}]"

        # Compute total duration across steps
        total_ms = sum(s.duration_ms for s in plan.steps)
        if total_ms < 1000:
            duration = f"{total_ms:.0f} ms"
        else:
            duration = f"{total_ms / 1000:.1f} s"

        completed = sum(1 for s in plan.steps if s.state == TaskState.COMPLETED)
        steps_str = f"[green]{completed}[/green]/[white]{len(plan.steps)}[/white]"

        table.add_row(
            plan.task_id,
            Text(plan.goal, overflow="fold"),
            steps_str,
            status_text,
            duration,
        )

    if not plans:
        table.add_row("—", "[dim]No tasks yet[/dim]", "—", "—", "—")

    return table


def _build_step_table(plan: Optional[TaskPlan]) -> Table:
    """Build a detailed step breakdown for the currently active plan."""
    table = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold bright_blue",
        border_style="bright_black",
        expand=True,
    )
    table.add_column("#", width=4, justify="right", style="dim")
    table.add_column("Step", ratio=2)
    table.add_column("Tool", width=22)
    table.add_column("Status", width=22)
    table.add_column("Retry", width=6, justify="center")
    table.add_column("Duration", width=10, justify="right")

    if plan is None:
        table.add_row("—", "[dim]No active plan[/dim]", "—", "—", "—", "—")
        return table

    for idx, step in enumerate(plan.steps, start=1):
        icon, style = STATE_STYLES.get(step.state, ("?", "white"))
        status_markup = f"[{style}]{icon} {step.state.value}[/{style}]"

        retry_str = f"[yellow]{step.retry_count}[/yellow]" if step.retry_count > 0 else "[dim]0[/dim]"
        duration = f"{step.duration_ms:.0f} ms" if step.duration_ms > 0 else "[dim]—[/dim]"

        error_hint = ""
        if step.error:
            short_err = step.error[:60] + "…" if len(step.error) > 60 else step.error
            error_hint = f"\n[dim red]{short_err}[/dim red]"
        if step.failure_analysis and step.failure_analysis.recovery_suggestion:
            hint = step.failure_analysis.recovery_suggestion[:70] + "…" if len(step.failure_analysis.recovery_suggestion) > 70 else step.failure_analysis.recovery_suggestion
            error_hint += f"\n[dim yellow]💡 {hint}[/dim yellow]"

        table.add_row(
            str(idx),
            Text(step.description + error_hint, overflow="fold"),
            f"[cyan]{step.tool_name}[/cyan]",
            status_markup,
            retry_str,
            duration,
        )

    return table


# ─────────────────────────────────────────────────────────────────────────────
# Telemetry bar
# ─────────────────────────────────────────────────────────────────────────────

def _build_telemetry_panel(agent: "NeronAgent") -> Panel:
    """Build a live system telemetry bar."""
    try:
        t = agent.os_controller.get_telemetry()
        cpu_bar = "█" * int(t.cpu_percent / 10) + "░" * (10 - int(t.cpu_percent / 10))
        ram_bar = "█" * int(t.memory_percent / 10) + "░" * (10 - int(t.memory_percent / 10))

        cpu_color = "green" if t.cpu_percent < 60 else "yellow" if t.cpu_percent < 85 else "red"
        ram_color = "green" if t.memory_percent < 60 else "yellow" if t.memory_percent < 85 else "red"

        content = (
            f"[{cpu_color}]CPU [{cpu_bar}] {t.cpu_percent:.0f}%[/{cpu_color}]  "
            f"[{ram_color}]RAM [{ram_bar}] {t.memory_percent:.0f}% ({t.memory_used_gb}/{t.memory_total_gb} GB)[/{ram_color}]  "
            f"[dim]OS: {t.os_name} {t.os_version}[/dim]  "
            f"[dim]Time: {datetime.now().strftime('%H:%M:%S')}[/dim]"
        )
    except Exception:
        content = "[dim]Telemetry unavailable[/dim]"

    return Panel(Align.center(content), style="bright_black", height=3)


# ─────────────────────────────────────────────────────────────────────────────
# Main Console class
# ─────────────────────────────────────────────────────────────────────────────

class NeronConsole:
    """
    Rich live-updating desktop console for Neron.

    Shows:
    - System telemetry bar
    - Active task plan with step breakdown
    - Recent task history table
    - Scrollable response text
    """

    def __init__(self, agent: "NeronAgent"):
        self.agent = agent
        self._console = Console(highlight=True)
        self._plans: List[TaskPlan] = []
        self._current_plan: Optional[TaskPlan] = None
        self._responses: List[str] = []
        self._lock = threading.Lock()

    def record_plan(self, plan: TaskPlan) -> None:
        """Register a plan for display (call before execution starts)."""
        with self._lock:
            self._current_plan = plan
            if plan not in self._plans:
                self._plans.append(plan)

    def record_response(self, text: str) -> None:
        """Store a response line for display in the output panel."""
        with self._lock:
            self._responses.append(text)
            if len(self._responses) > 50:
                self._responses.pop(0)

    def clear_active(self) -> None:
        """Mark that no plan is currently executing."""
        with self._lock:
            self._current_plan = None

    def _build_layout(self) -> Layout:
        """Build the full console layout."""
        layout = Layout(name="root")
        layout.split_column(
            Layout(name="telemetry", size=3),
            Layout(name="body", ratio=1),
            Layout(name="response", size=10),
        )
        layout["body"].split_row(
            Layout(name="history", ratio=1),
            Layout(name="active", ratio=1),
        )
        return layout

    def _render(self, layout: Layout) -> None:
        """Update all layout regions with fresh data."""
        with self._lock:
            plans_snapshot = list(self._plans)
            current = self._current_plan
            responses = list(self._responses)

        # Telemetry bar
        layout["telemetry"].update(_build_telemetry_panel(self.agent))

        # Task history
        plan_table = _build_plan_table(plans_snapshot)
        layout["history"].update(Panel(
            plan_table,
            title="[bold cyan]📋 Task History[/bold cyan]",
            border_style="cyan",
        ))

        # Active plan steps
        step_table = _build_step_table(current)
        title_suffix = f"[dim] — {current.goal[:40]}[/dim]" if current else ""
        layout["active"].update(Panel(
            step_table,
            title=f"[bold bright_blue]⚡ Active Plan{title_suffix}[/bold bright_blue]",
            border_style="bright_blue",
        ))

        # Response area
        response_lines = responses[-8:] if responses else ["[dim]Waiting for input…[/dim]"]
        response_text = "\n".join(f"[bright_white]{r}[/bright_white]" for r in response_lines)
        layout["response"].update(Panel(
            response_text,
            title="[bold green]💬 Neron[/bold green]",
            border_style="green",
        ))

    def run_live_loop(self, stop_event: threading.Event, refresh_hz: float = 2.0) -> None:
        """
        Run the live updating console loop until stop_event is set.

        This is intended to be run in a background thread while the main thread
        handles user input.
        """
        if not RICH_AVAILABLE:
            return

        layout = self._build_layout()
        with Live(layout, console=self._console, refresh_per_second=refresh_hz, screen=True):
            while not stop_event.is_set():
                self._render(layout)
                time.sleep(1.0 / refresh_hz)

    def print_response(self, text: str) -> None:
        """Print a response to the console (without live mode)."""
        self._console.print(f"[bold green]Neron ▶[/bold green] {text}")

    def print_error(self, text: str) -> None:
        """Print an error to the console."""
        self._console.print(f"[bold red]✖[/bold red] {text}")

    def print_info(self, text: str) -> None:
        """Print an informational message."""
        self._console.print(f"[dim cyan]ℹ[/dim cyan] {text}")

    def print_plan_summary(self, plan: TaskPlan) -> None:
        """Print a compact plan summary after execution completes."""
        if not RICH_AVAILABLE:
            return
        self._console.print()
        self._console.print(Panel(
            _build_step_table(plan),
            title=f"[bold]Plan Complete — {plan.state.value}[/bold]",
            border_style="green" if plan.state == TaskState.COMPLETED else "red",
        ))
        if plan.rollback_log:
            self._console.print("[yellow]⚠ Rollback log:[/yellow]")
            for entry in plan.rollback_log:
                self._console.print(f"  [dim yellow]↩ {entry}[/dim yellow]")
        if plan.warnings:
            self._console.print("[yellow]⚠ Warnings:[/yellow]")
            for w in plan.warnings:
                self._console.print(f"  [dim yellow]⚡ {w}[/dim yellow]")

    def print_banner(self) -> None:
        """Print the Neron startup banner."""
        if not RICH_AVAILABLE:
            print("NERON — Modular Local-First Computer Agent")
            return

        t = None
        try:
            t = self.agent.os_controller.get_telemetry()
        except Exception:
            pass

        tool_count = len(self.agent.tool_registry.list_tools())
        mode = self.agent.permission_manager.mode.value

        banner_art = """
  ███╗   ██╗███████╗██████╗  ██████╗ ███╗   ██╗
  ████╗  ██║██╔════╝██╔══██╗██╔═══██╗████╗  ██║
  ██╔██╗ ██║█████╗  ██████╔╝██║   ██║██╔██╗ ██║
  ██║╚██╗██║██╔══╝  ██╔══██╗██║   ██║██║╚██╗██║
  ██║ ╚████║███████╗██║  ██║╚██████╔╝██║ ╚████║
  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
""".strip("\n")

        self._console.print(Panel(
            Align.center(
                f"[bright_cyan bold]{banner_art}[/bright_cyan bold]\n\n"
                f"[dim]Modular Local-First AI Computer Agent[/dim]"
            ),
            border_style="cyan",
            padding=(1, 4),
        ))

        info_table = Table(box=box.SIMPLE, show_header=False, border_style="bright_black")
        info_table.add_column(style="dim cyan", width=16)
        info_table.add_column()

        if t:
            info_table.add_row("OS", f"{t.os_name} {t.os_version}")
            info_table.add_row("CPU / RAM", f"{t.cpu_percent:.0f}% CPU | {t.memory_percent:.0f}% RAM ({t.memory_used_gb}/{t.memory_total_gb} GB)")

        info_table.add_row("Security", f"[green]{mode}[/green] mode")
        info_table.add_row("Tools loaded", f"[cyan]{tool_count}[/cyan]")
        info_table.add_row("Wake Hotkey", "[yellow]SHIFT+L[/yellow]")
        info_table.add_row("Voice Wake", "[yellow]'Hey Neron' or 'Neron'[/yellow]")
        info_table.add_row("Emergency Stop", "[yellow]CTRL+ALT+N[/yellow]")
        info_table.add_row("Exit", "[yellow]'exit' or CTRL+C[/yellow]")

        self._console.print(Align.center(info_table))
        self._console.print()
