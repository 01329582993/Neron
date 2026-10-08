"""NERON Command Line Interface & Interactive Desktop Console — Stage 7."""

from __future__ import annotations

import argparse
import sys
import threading

from neron.config.manager import ConfigManager
from neron.core.agent.base import NeronAgent
from neron.core.executor.dag_executor import DAGExecutor
from neron.core.planner.dag_planner import DAGPlanner
from neron.diagnostics.health import HealthManager, run_cli_diagnostics
from neron.security.permissions import SecurityMode
from neron.ui.console import NeronConsole, RICH_AVAILABLE
from neron.utils.audit import AuditLedger
from neron.utils.logger import setup_logging

# Configure standard streams for UTF-8 on Windows
if sys.platform.startswith("win"):
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Diagnostics & Audit (plain text, no Rich required)
# ─────────────────────────────────────────────────────────────────────────────

def run_diagnostics() -> None:
    """Run system diagnostics report (delegates to HealthManager)."""
    run_cli_diagnostics()


def show_audit_history(limit: int = 20) -> None:
    ledger = AuditLedger()
    events = ledger.get_recent_events(limit=limit)
    print(f"\n--- Recent Security & Tool Audit Events ({len(events)}) ---")
    if not events:
        print("No audit events recorded yet.")
        return
    for ev in events:
        status = "SUCCESS" if ev["success"] else "FAIL"
        print(f"[{ev['timestamp']}] {ev['tool_name']} ({ev['decision']}) -> {status} [{ev['duration_ms']:.1f}ms]")
        if ev.get("result_summary"):
            print(f"   Summary: {ev['result_summary'][:100]}")


# ─────────────────────────────────────────────────────────────────────────────
# Rich REPL
# ─────────────────────────────────────────────────────────────────────────────

def interactive_repl(agent: NeronAgent) -> None:
    """Main interactive REPL with Rich console UI and DAG planner/executor."""
    console = NeronConsole(agent)
    dag_planner = DAGPlanner()
    dag_executor = DAGExecutor(
        tool_registry=agent.tool_registry,
        event_bus=agent.event_bus,
        emergency_stop=agent.emergency_stop,
    )

    console.print_banner()

    # ── Help text ─────────────────────────────────────────────────────────────
    help_text = """
[bold cyan]Console Commands:[/bold cyan]
  [yellow]status[/yellow]         Live system telemetry
  [yellow]health[/yellow]         Run self-diagnostics
  [yellow]tools[/yellow]          List all registered tools
  [yellow]audit[/yellow]          View security audit log
  [yellow]mode <MODE>[/yellow]    Switch security mode (SAFE / STANDARD / POWER_USER)
  [yellow]stop[/yellow]           Trigger emergency stop
  [yellow]reset-stop[/yellow]     Reset emergency stop
  [yellow]exit[/yellow]           Quit Neron

[bold cyan]Natural Language Examples:[/bold cyan]
  "what is using all my ram?"
  "open notepad"
  "set volume to 40"
  "prepare development environment"
  "check system then open chrome"
  "search for my machine learning project then open it"
""" if RICH_AVAILABLE else ""

    while True:
        try:
            prompt_str = "\nneron> " if not RICH_AVAILABLE else "\n[bold green]neron[/bold green]> "

            if RICH_AVAILABLE:
                from rich.console import Console as _RC
                _c = _RC()
                _c.print(prompt_str, end="")
                user_input = input("").strip()
            else:
                user_input = input(prompt_str).strip()

            if not user_input:
                continue

            lower = user_input.lower().strip()

            # ── Built-in commands ─────────────────────────────────────────────
            if lower in ("exit", "quit", "q"):
                console.print_info("Shutting down Neron. Goodbye.")
                break

            elif lower == "help":
                if RICH_AVAILABLE:
                    from rich.console import Console as _RC
                    _RC().print(help_text)
                else:
                    print("Commands: status, health, tools, audit, mode <MODE>, stop, reset-stop, exit")
                continue

            elif lower == "status":
                t = agent.os_controller.get_telemetry()
                w = agent.os_controller.get_active_window()
                console.print_info(
                    f"CPU: {t.cpu_percent:.0f}% | RAM: {t.memory_used_gb}/{t.memory_total_gb} GB "
                    f"({t.memory_percent:.0f}%) | Disk Free: {t.disk_free_gb} GB"
                )
                if w:
                    console.print_info(f"Active Window: '{w.title}' (Process: {w.process_name})")
                continue

            elif lower == "health":
                run_diagnostics()
                continue

            elif lower == "tools":
                tools = agent.tool_registry.list_tools()
                console.print_info(f"Registered Tools ({len(tools)}):")
                for t in tools:
                    caps = ", ".join(t.required_capabilities)
                    console.print_info(f"  • {t.name:<22} [{caps}] — {t.description}")
                continue

            elif lower == "audit":
                show_audit_history(limit=15)
                continue

            elif lower.startswith("mode "):
                mode_str = lower.split(" ", 1)[1].strip().upper()
                try:
                    new_mode = SecurityMode(mode_str)
                    agent.permission_manager.set_mode(new_mode)
                    console.print_response(f"Security mode updated to [bold]{new_mode.value}[/bold]")
                except ValueError:
                    console.print_error("Invalid mode. Choose: SAFE, STANDARD, POWER_USER, CUSTOM")
                continue

            elif lower == "stop":
                agent.stop("User invoked stop command from console")
                console.print_error("Emergency stop triggered! Active operations cancelled.")
                continue

            elif lower == "reset-stop":
                agent.reset_stop()
                console.print_response("Emergency stop reset. System ready.")
                continue

            # ── Natural Language Goal ─────────────────────────────────────────
            console.print_info(f"Processing: '{user_input}'")

            # Build plan using DAGPlanner
            context = {"platform": sys.platform}
            plan = dag_planner.plan(
                goal=user_input,
                context=context,
                available_tools=agent.tool_registry.list_tools(),
            )
            console.record_plan(plan)

            # Execute with DAGExecutor
            result_plan = dag_executor.execute_plan(plan)
            console.clear_active()

            # Print rich summary
            console.print_plan_summary(result_plan)

            # Extract and print the most relevant result
            if result_plan.state.value == "COMPLETED":
                for step in result_plan.steps:
                    if step.result is not None:
                        res_str = str(step.result)
                        if len(res_str) > 300:
                            res_str = res_str[:300] + "…"
                        console.print_response(res_str)
                        console.record_response(res_str)
            else:
                if result_plan.error:
                    console.print_error(f"Plan failed: {result_plan.error}")
                for step in result_plan.steps:
                    if step.failure_analysis:
                        console.print_error(
                            f"[{step.failure_analysis.mode.value}] {step.failure_analysis.recovery_suggestion}"
                        )

        except (KeyboardInterrupt, EOFError):
            console.print_info("\nInterrupt received. Exiting.")
            break
        except Exception as e:
            console.print_error(f"Unexpected error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    # ── Handle 'neron plugin create <name>' subcommand ─────────────────────────
    if len(sys.argv) > 1 and sys.argv[1] == "plugin":
        sub_parser = argparse.ArgumentParser(prog="neron plugin", description="Neron plugin management")
        sub_sub = sub_parser.add_subparsers(dest="subcommand")
        create_p = sub_sub.add_parser("create", help="Create a new plugin scaffold")
        create_p.add_argument("name", help="Plugin name or ID")
        create_p.add_argument("--desc", default="A community extension for Neron.", help="Plugin description")
        create_p.add_argument("--tool", default=None, help="Initial tool ID")
        sub_args = sub_parser.parse_args(sys.argv[2:])
        if sub_args.subcommand == "create":
            from neron.developer.scaffolder import PluginScaffolder, PluginScaffoldConfig
            scaffolder = PluginScaffolder()
            plugin_id = sub_args.name.lower().replace(" ", "_")
            cfg = PluginScaffoldConfig(
                plugin_id=plugin_id,
                name=sub_args.name,
                description=sub_args.desc,
                tool_name=sub_args.tool,
            )
            created = scaffolder.create_plugin_scaffold(cfg)
            print(f"Successfully created plugin '{plugin_id}' at: {created['directory']}")
            sys.exit(0)
        else:
            sub_parser.print_help()
            sys.exit(1)

    parser = argparse.ArgumentParser(description="NERON — Modular Local-First Computer Agent")
    parser.add_argument("--diagnose", action="store_true", help="Run system diagnostics and exit")
    parser.add_argument("--audit-history", action="store_true", help="Display recent security audit log")
    parser.add_argument("--test", nargs="?", const="all", help="Run automated test suite (optionally specify test target)")
    parser.add_argument("--inspect", type=str, help="Inspect source structure of a module or file")
    parser.add_argument(
        "--security", type=str,
        choices=["SAFE", "STANDARD", "POWER_USER", "CUSTOM"],
        help="Set security mode",
    )
    parser.add_argument("-g", "--goal", type=str, help="Execute a goal directly and exit")
    args = parser.parse_args()

    setup_logging()

    if args.diagnose:
        run_diagnostics()
        return

    if args.audit_history:
        show_audit_history()
        return

    if args.test:
        from neron.developer.test_runner import TestRunner
        runner = TestRunner()
        target = None if args.test == "all" else args.test
        print(f"Executing Neron test suite{f' ({target})' if target else ''}...")
        res = runner.run_tests(target=target)
        print(f"Results: {res.passed} passed, {res.failed} failed, {res.skipped} skipped in {res.duration_seconds}s")
        if res.error_summary:
            for err in res.error_summary:
                print(f"  [FAIL] {err}")
        sys.exit(0 if res.success else 1)

    if args.inspect:
        from pathlib import Path
        from neron.developer.introspector import CodeIntrospector
        introspector = CodeIntrospector()
        target = args.inspect
        p = Path(target)
        if p.is_file() or (Path.cwd() / target).is_file():
            info = introspector.inspect_file(p if p.is_file() else (Path.cwd() / target))
        else:
            info = introspector.inspect_module(target)
        print(f"\n--- Code Introspection: {target} ---")
        print(f"Total lines: {info.get('total_lines')}")
        print(f"Docstring: {info.get('module_docstring')}")
        print(f"Classes ({len(info.get('classes', []))}):")
        for c in info.get("classes", []):
            print(f"  - {c['name']} (lines {c['lineno']}-{c['end_lineno']}): {len(c.get('methods', []))} methods")
        print(f"Functions ({len(info.get('functions', []))}):")
        for f in info.get("functions", []):
            print(f"  - {f['name']} (lines {f['lineno']}-{f['end_lineno']})")
        print(f"Imports ({len(info.get('imports', []))}):")
        for imp in info.get("imports", []):
            print(f"  - {imp}")
        return

    cfg_mgr = ConfigManager()
    if args.security:
        cfg_mgr.config.security.profile = args.security

    agent = NeronAgent(config_manager=cfg_mgr)

    if args.goal:
        console = NeronConsole(agent)
        dag_planner = DAGPlanner()
        dag_executor = DAGExecutor(
            tool_registry=agent.tool_registry,
            event_bus=agent.event_bus,
            emergency_stop=agent.emergency_stop,
        )
        context = {"platform": sys.platform}
        plan = dag_planner.plan(goal=args.goal, context=context, available_tools=agent.tool_registry.list_tools())
        result = dag_executor.execute_plan(plan)
        console.print_plan_summary(result)
        sys.exit(0 if result.state.value == "COMPLETED" else 1)

    interactive_repl(agent)


if __name__ == "__main__":
    main()
