"""NERON Command Line Interface & Interactive Desktop Console."""

import argparse
import sys
from neron.config.manager import ConfigManager
from neron.core.agent.base import NeronAgent
from neron.diagnostics.health import HealthManager
from neron.security.permissions import SecurityMode
from neron.utils.audit import AuditLedger
from neron.utils.logger import setup_logging

try:
    from colorama import Fore, Style
    COLOR = True
except ImportError:
    COLOR = False


# Configure standard streams for UTF-8 on Windows
if sys.platform.startswith("win"):
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def print_banner(agent: NeronAgent) -> None:
    cyan = Fore.CYAN if COLOR else ""
    green = Fore.GREEN if COLOR else ""
    yellow = Fore.YELLOW if COLOR else ""
    reset = Style.RESET_ALL if COLOR else ""

    telemetry = agent.os_controller.get_telemetry()
    tools_count = len(agent.tool_registry.list_tools())
    mode = agent.permission_manager.mode.value

    print(f"{cyan}")
    print(r"  _   _ _____ ____   ___  _   _ ")
    print(r" | \ | | ____|  _ \ / _ \| \ | |")
    print(r" |  \| |  _| | |_) | | | |  \| |")
    print(r" | |\  | |___|  _ <| |_| | |\  |")
    print(r" |_| \_|_____|_| \_\\___/|_| \_|")
    print(f" Modular Local-First Computer Agent{reset}\n")

    print(f" [*] OS:       {telemetry.os_name} {telemetry.os_version}")
    print(f" [*] CPU/RAM:  {telemetry.cpu_percent}% CPU | {telemetry.memory_percent}% RAM ({telemetry.memory_used_gb}/{telemetry.memory_total_gb} GB)")
    print(f" [*] Security: {green}{mode}{reset} mode active (Emergency Stop: {yellow}CTRL+ALT+N{reset})")
    print(f" [*] Registry: {tools_count} built-in tools loaded and verified")
    print(f" Type {yellow}help{reset} for commands, or describe what you want Neron to do.")
    print("-" * 65)


def run_diagnostics() -> None:
    """Run system diagnostics report."""
    print("==================================================")
    print("           NERON SYSTEM DIAGNOSTICS")
    print("==================================================")
    manager = HealthManager()
    results = manager.run_full_diagnostics()

    green = Fore.GREEN if COLOR else ""
    yellow = Fore.YELLOW if COLOR else ""
    red = Fore.RED if COLOR else ""
    reset = Style.RESET_ALL if COLOR else ""

    for res in results:
        if res.status == "HEALTHY":
            badge = f"{green}[OK HEALTHY]{reset}"
        elif res.status in ("WARNING", "DEGRADED"):
            badge = f"{yellow}[WARN {res.status}]{reset}"
        else:
            badge = f"{red}[FAIL {res.status}]{reset}"

        print(f"\n{badge} {res.name}")
        print(f"   Details: {res.details}")
        if res.remediation_hint:
            print(f"   Fix:     {res.remediation_hint}")
    print("\n" + "=" * 50)


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


def interactive_repl(agent: NeronAgent) -> None:
    print_banner(agent)
    yellow = Fore.YELLOW if COLOR else ""
    green = Fore.GREEN if COLOR else ""
    red = Fore.RED if COLOR else ""
    reset = Style.RESET_ALL if COLOR else ""

    while True:
        try:
            prompt_str = f"\n{green}neron{reset}> "
            user_input = input(prompt_str).strip()
            if not user_input:
                continue

            lower = user_input.lower()
            if lower in ("exit", "quit", "q"):
                print("Shutting down Neron console. Goodbye.")
                break

            elif lower == "help":
                print("\nAvailable Console Commands:")
                print("  status        - View system telemetry and active window")
                print("  health        - Run self-diagnostics")
                print("  tools         - List all registered tools and required capabilities")
                print("  audit         - View recent security audit log entries")
                print("  mode <MODE>   - Switch security mode (SAFE, STANDARD, POWER_USER)")
                print("  stop          - Trigger emergency stop")
                print("  reset-stop    - Reset emergency stop state")
                print("  exit / quit   - Exit console")
                print("\nNatural Language Examples:")
                print("  'what is using all my ram?'")
                print("  'open notepad'")
                print("  'close notepad'")
                print("  'set volume to 40'")
                print("  'find my machine learning project'")
                print("  'create a folder called Research'")
                continue

            elif lower == "status":
                t = agent.os_controller.get_telemetry()
                w = agent.os_controller.get_active_window()
                print(f"CPU: {t.cpu_percent}% | RAM: {t.memory_used_gb}/{t.memory_total_gb} GB ({t.memory_percent}%) | Disk Free: {t.disk_free_gb} GB")
                if w:
                    print(f"Active Window: '{w.title}' (Process: {w.process_name})")
                continue

            elif lower == "health":
                run_diagnostics()
                continue

            elif lower == "tools":
                tools = agent.tool_registry.list_tools()
                print(f"\nRegistered Tools ({len(tools)}):")
                for t in tools:
                    caps = ", ".join(t.required_capabilities)
                    print(f"  • {yellow}{t.name:<22}{reset} [{caps}] - {t.description}")
                continue

            elif lower == "audit":
                show_audit_history(limit=15)
                continue

            elif lower.startswith("mode "):
                mode_str = lower.split(" ", 1)[1].strip().upper()
                try:
                    new_mode = SecurityMode(mode_str)
                    agent.permission_manager.set_mode(new_mode)
                    print(f"Security mode updated to {green}{new_mode.value}{reset}")
                except ValueError:
                    print(f"{red}Invalid mode. Choose from: SAFE, STANDARD, POWER_USER, CUSTOM{reset}")
                continue

            elif lower == "stop":
                agent.stop("User invoked stop command from console")
                print(f"{red}Emergency stop triggered! Active operations cancelled.{reset}")
                continue

            elif lower == "reset-stop":
                agent.reset_stop()
                print("Emergency stop reset. System ready.")
                continue

            # Process Goal
            print(f"[*] Processing goal: '{user_input}'...")
            plan = agent.run_goal(user_input)

            state_color = green if plan.state.value == "COMPLETED" else red
            print(f"\nTask Result: {state_color}{plan.state.value}{reset}")
            for idx, step in enumerate(plan.steps):
                step_badge = "[OK]" if step.state.value == "COMPLETED" else "[X]"
                print(f"  {step_badge} Step {idx + 1}: {step.description} ({step.duration_ms:.1f}ms)")
                if step.error:
                    print(f"      {red}Error: {step.error}{reset}")
                elif step.result is not None:
                    # Compact result print
                    res_str = str(step.result)
                    if len(res_str) > 120:
                        res_str = res_str[:120] + "..."
                    print(f"      Result: {res_str}")

        except (KeyboardInterrupt, EOFError):
            print("\nInterrupt received. Exiting...")
            break
        except Exception as e:
            print(f"{red}Error: {e}{reset}")


def main() -> None:
    parser = argparse.ArgumentParser(description="NERON — Modular Local-First Computer Agent")
    parser.add_argument("--diagnose", action="store_true", help="Run system diagnostics and exit")
    parser.add_argument("--audit-history", action="store_true", help="Display recent security audit log")
    parser.add_argument("--security", type=str, choices=["SAFE", "STANDARD", "POWER_USER", "CUSTOM"], help="Set security mode")
    parser.add_argument("-g", "--goal", type=str, help="Execute a goal directly and exit")
    args = parser.parse_args()

    # Initialize logging
    setup_logging()

    if args.diagnose:
        run_diagnostics()
        return

    if args.audit_history:
        show_audit_history()
        return

    # Initialize Agent
    cfg_mgr = ConfigManager()
    if args.security:
        cfg_mgr.config.security.profile = args.security

    agent = NeronAgent(config_manager=cfg_mgr)

    if args.goal:
        print(f"Executing goal: '{args.goal}'")
        plan = agent.run_goal(args.goal)
        print(f"Status: {plan.state.value}")
        sys.exit(0 if plan.state.value == "COMPLETED" else 1)

    interactive_repl(agent)


if __name__ == "__main__":
    main()
