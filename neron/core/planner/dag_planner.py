"""DAG-aware task planner — decomposes goals into multi-step dependency graphs."""

import re
from typing import Any, Dict, List
from neron.core.planner.base import BasePlanner
from neron.core.state.models import PlanStep, TaskPlan, TaskState
from neron.tools.base import BaseTool
from neron.utils.logger import get_logger

logger = get_logger("core.dag_planner")


class DAGPlanner(BasePlanner):
    """
    Produces multi-step TaskPlans with explicit DAG dependencies.

    Each step has a `depends_on` list of step_ids that must complete first.
    This allows the DAGExecutor to determine safe execution ordering and
    skip/cancel downstream steps when a dependency fails.
    """

    def plan(
        self,
        goal: str,
        context: Dict[str, Any],
        available_tools: List[BaseTool],
    ) -> TaskPlan:
        clean = goal.strip()
        lower = clean.lower()

        plan = TaskPlan(goal=clean, state=TaskState.PLANNING)

        # ── Pattern: Procedural Automation Recipes ─────────────────────────
        recipe_mgr = context.get("recipe_manager")
        if recipe_mgr:
            matched_recipe = recipe_mgr.find_matching_recipe(clean)
            if matched_recipe:
                steps_data = matched_recipe.get("steps", [])
                plan.steps = [
                    PlanStep(
                        tool_name=s.get("tool_name"),
                        arguments=s.get("arguments", {}),
                        description=s.get("description", "Execute recipe step"),
                        depends_on=s.get("depends_on", []),
                        is_optional=s.get("is_optional", False),
                    )
                    for s in steps_data
                ]
                plan.state = TaskState.PENDING
                return plan

        # ── Pattern: "remember (that) X is Y" ──────────────────────────────
        rem_match = re.search(r"remember\s+(?:that\s+)?(.+?)\s+is\s+(.+)$", lower)
        if rem_match:
            k = rem_match.group(1).strip()
            v = rem_match.group(2).strip()
            plan.steps = [
                PlanStep(
                    tool_name="memory.remember",
                    arguments={"key": k, "value": v},
                    description=f"Remember that '{k}' is '{v}'",
                )
            ]
            plan.state = TaskState.PENDING
            return plan

        # ── Pattern: "recall X" / "what is my X" ────────────────────────────
        recall_match = re.search(r"^(?:recall|what\s+is\s+(?:my\s+)?)(.+)$", lower)
        if recall_match and not any(kw in lower for kw in ["time", "weather", "volume", "cpu", "ram"]):
            k = recall_match.group(1).strip().rstrip("?")
            plan.steps = [
                PlanStep(
                    tool_name="memory.recall",
                    arguments={"key": k},
                    description=f"Recall '{k}' from memory",
                )
            ]
            plan.state = TaskState.PENDING
            return plan

        # ── Pattern: "forget X" ─────────────────────────────────────────────
        forget_match = re.search(r"^forget\s+(?:that\s+)?(.+)$", lower)
        if forget_match:
            k = forget_match.group(1).strip()
            plan.steps = [
                PlanStep(
                    tool_name="memory.forget",
                    arguments={"key": k},
                    description=f"Forget '{k}' from memory",
                )
            ]
            plan.state = TaskState.PENDING
            return plan


        # ── Pattern: "prepare development environment" ─────────────────────
        if "prepare" in lower and "dev" in lower:
            telemetry_step = PlanStep(
                tool_name="system.telemetry",
                arguments={},
                description="Check system resources before starting dev environment",
            )
            open_vscode = PlanStep(
                tool_name="system.open_app",
                arguments={"app_name": "code"},
                description="Open Visual Studio Code",
                depends_on=[telemetry_step.step_id],
            )
            plan.steps = [telemetry_step, open_vscode]
            plan.state = TaskState.PENDING
            return plan

        # ── Pattern: "write file X with content Y then read it back" ───────
        write_read = re.search(
            r"write\s+(?:file\s+)?['\"]?(.+?)['\"]?\s+with\s+content\s+['\"]?(.+?)['\"]?\s+(?:then|and)\s+read",
            lower,
        )
        if write_read:
            path = write_read.group(1).strip()
            content = write_read.group(2).strip()
            write_step = PlanStep(
                tool_name="filesystem.write",
                arguments={"path": path, "content": content},
                description=f"Write content to file '{path}'",
            )
            read_step = PlanStep(
                tool_name="filesystem.read",
                arguments={"path": path},
                description=f"Read back file '{path}' to verify write",
                depends_on=[write_step.step_id],
            )
            plan.steps = [write_step, read_step]
            plan.state = TaskState.PENDING
            return plan

        # ── Pattern: "check system then open X" ────────────────────────────
        check_then = re.search(
            r"(?:check|inspect)\s+system\s+(?:then|and)\s+(?:open|launch|start)\s+(.+)", lower
        )
        if check_then:
            app = check_then.group(1).strip()
            telem = PlanStep(
                tool_name="system.telemetry",
                arguments={},
                description="Inspect system load before launching application",
            )
            launch = PlanStep(
                tool_name="system.open_app",
                arguments={"app_name": app},
                description=f"Launch '{app}'",
                depends_on=[telem.step_id],
            )
            plan.steps = [telem, launch]
            plan.state = TaskState.PENDING
            return plan

        # ── Pattern: "search for X then open the first result" ─────────────
        search_open = re.search(r"search\s+(?:for\s+)?(.+?)\s+(?:then|and)\s+open", lower)
        if search_open:
            query = search_open.group(1).strip()
            search = PlanStep(
                tool_name="filesystem.search",
                arguments={"query": query},
                description=f"Search for '{query}'",
            )
            open_app = PlanStep(
                tool_name="system.open_app",
                arguments={"app_name": query},
                description=f"Open result matching '{query}'",
                depends_on=[search.step_id],
                is_optional=True,   # might not find anything
            )
            plan.steps = [search, open_app]
            plan.state = TaskState.PENDING
            return plan

        # ── Pattern: "click X then type Y" ─────────────────────────────────
        click_type = re.search(r"click\s+(?:on\s+)?(?:the\s+)?(.+?)\s+(?:then|and)\s+type\s+['\"]?(.+?)['\"]?$", lower)
        if click_type:
            target = click_type.group(1).strip()
            text_to_type = click_type.group(2).strip()
            click_step = PlanStep(
                tool_name="vision.click_element",
                arguments={"description": target},
                description=f"Click target '{target}'",
            )
            type_step = PlanStep(
                tool_name="vision.type_text",
                arguments={"text": text_to_type, "press_enter": True},
                description=f"Type '{text_to_type}'",
                depends_on=[click_step.step_id],
            )
            plan.steps = [click_step, type_step]
            plan.state = TaskState.PENDING
            return plan

        # ── Pattern: "click (on) the X (button)" ───────────────────────────
        click_match = re.search(r"^click\s+(?:on\s+)?(?:the\s+)?(.+)", lower)
        if click_match and "then" not in lower and "and" not in lower:
            target = click_match.group(1).strip()
            find_step = PlanStep(
                tool_name="vision.find_element",
                arguments={"description": target},
                description=f"Locate '{target}' visually on screen",
            )
            click_step = PlanStep(
                tool_name="vision.click_element",
                arguments={"description": target},
                description=f"Click '{target}'",
                depends_on=[find_step.step_id],
            )
            plan.steps = [find_step, click_step]
            plan.state = TaskState.PENDING
            return plan


        # ── Fallback: single-step via heuristics ───────────────────────────
        plan = self._heuristic_single_step(clean, lower, context)
        return plan

    def _heuristic_single_step(self, clean: str, lower: str, context: Dict[str, Any]) -> TaskPlan:
        """Single-step heuristic fallback — same logic as HeuristicPlanner."""
        plan = TaskPlan(goal=clean, state=TaskState.PLANNING)

        if any(kw in lower for kw in ["ram", "cpu", "memory", "telemetry", "hardware", "disk space", "battery"]):
            plan.steps.append(PlanStep(tool_name="system.telemetry", arguments={}, description="Check system hardware"))
            plan.state = TaskState.PENDING
            return plan

        vol_match = re.search(r"set volume to (\d+)", lower)
        if vol_match:
            plan.steps.append(PlanStep(
                tool_name="system.volume",
                arguments={"level": int(vol_match.group(1))},
                description=f"Set volume to {vol_match.group(1)}%",
            ))
            plan.state = TaskState.PENDING
            return plan

        if "volume" in lower and any(kw in lower for kw in ["get", "what", "check"]):
            plan.steps.append(PlanStep(tool_name="system.volume", arguments={}, description="Query current volume"))
            plan.state = TaskState.PENDING
            return plan

        open_match = re.search(r"(?:open|launch|start)\s+([a-zA-Z0-9\s_\-\.]+)", lower)
        if open_match and "folder" not in lower and "file" not in lower:
            app = re.sub(r"\b(app|application|please)\b", "", open_match.group(1)).strip()
            plan.steps.append(PlanStep(tool_name="system.open_app", arguments={"app_name": app}, description=f"Launch '{app}'"))
            plan.state = TaskState.PENDING
            return plan

        close_match = re.search(r"(?:close|kill|quit|terminate)\s+([a-zA-Z0-9\s_\-\.]+)", lower)
        if close_match and "folder" not in lower and "file" not in lower:
            app = re.sub(r"\b(app|application|please)\b", "", close_match.group(1)).strip()
            plan.steps.append(PlanStep(tool_name="system.close_app", arguments={"app_name": app}, description=f"Close '{app}'"))
            plan.state = TaskState.PENDING
            return plan

        if any(kw in lower for kw in ["screenshot", "capture screen", "screen capture", "take screenshot"]):
            plan.steps.append(PlanStep(tool_name="vision.screenshot", arguments={}, description="Capture desktop screenshot"))
            plan.state = TaskState.PENDING
            return plan

        type_match = re.search(r"^type\s+['\"]?(.+?)['\"]?$", lower)
        if type_match:
            text_str = type_match.group(1).strip()
            plan.steps.append(PlanStep(tool_name="vision.type_text", arguments={"text": text_str}, description=f"Type '{text_str}'"))
            plan.state = TaskState.PENDING
            return plan

        if "on screen" in lower and any(kw in lower for kw in ["find", "search", "locate"]):
            query = re.sub(r"^(?:hey\s+neron,?\s*)?(?:find|search(?:\s+for)?|where\s+is|locate)\s+", "", lower)
            query = re.sub(r"\s+on\s+screen.*$", "", query).strip()
            plan.steps.append(PlanStep(tool_name="vision.find_element", arguments={"description": query}, description=f"Locate '{query}' on screen"))
            plan.state = TaskState.PENDING
            return plan

        if any(kw in lower for kw in ["find", "search", "where is", "locate"]):
            query = re.sub(r"^(?:hey\s+neron,?\s*)?(?:find|search(?:\s+for)?|where\s+is|locate)\s+", "", lower).strip()
            plan.steps.append(PlanStep(tool_name="filesystem.search", arguments={"query": query}, description=f"Search for '{query}'"))
            plan.state = TaskState.PENDING
            return plan

        create_match = re.search(r"create (?:a )?folder (?:called |named )?([a-zA-Z0-9_\-\.]+)", lower)
        if create_match:
            folder = create_match.group(1).strip()
            cmd = f"New-Item -ItemType Directory -Force -Path '{folder}'" if context.get("platform") == "windows" else f"mkdir -p {folder}"
            plan.steps.append(PlanStep(tool_name="terminal.execute", arguments={"command": cmd}, description=f"Create folder '{folder}'"))
            plan.state = TaskState.PENDING
            return plan

        exec_match = re.search(r"(?:run|execute|exec)(?:\s+command)?\s+(.+)", clean, re.IGNORECASE)
        if exec_match:
            cmd = exec_match.group(1).strip()
            plan.steps.append(PlanStep(tool_name="terminal.execute", arguments={"command": cmd}, description=f"Execute: {cmd}"))
            plan.state = TaskState.PENDING
            return plan

        # Default fallback
        plan.steps.append(PlanStep(tool_name="filesystem.search", arguments={"query": clean}, description=f"Search: {clean}"))
        plan.state = TaskState.PENDING
        return plan
