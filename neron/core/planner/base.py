"""Task planning interfaces and heuristic/LLM plan generators."""

from abc import ABC, abstractmethod
import re
from typing import Any, Dict, List, Optional
from neron.core.state.models import PlanStep, TaskPlan, TaskState
from neron.tools.base import BaseTool
from neron.utils.logger import get_logger

logger = get_logger("core.planner")


class BasePlanner(ABC):
    """Abstract interface for decomposing goals into structured TaskPlans."""

    @abstractmethod
    def plan(
        self,
        goal: str,
        context: Dict[str, Any],
        available_tools: List[BaseTool]
    ) -> TaskPlan:
        pass


class HeuristicPlanner(BasePlanner):
    """Deterministic, offline-first intent and workflow planner."""

    def plan(
        self,
        goal: str,
        context: Dict[str, Any],
        available_tools: List[BaseTool]
    ) -> TaskPlan:
        clean_goal = goal.strip()
        lower_goal = clean_goal.lower()

        plan = TaskPlan(goal=clean_goal, state=TaskState.PLANNING)

        # 1. Multi-Step Composite Workflow: "Prepare development environment"
        if "prepare" in lower_goal and "dev" in lower_goal:
            plan.steps = [
                PlanStep(
                    tool_name="system.open_app",
                    arguments={"app_name": "code"},
                    description="Open Visual Studio Code",
                ),
                PlanStep(
                    tool_name="system.telemetry",
                    arguments={},
                    description="Inspect system load before dev server startup",
                ),
            ]
            plan.state = TaskState.PENDING
            return plan

        # 2. System Telemetry / "what's using all my RAM?" / "cpu" / "status"
        if any(kw in lower_goal for kw in ["ram", "cpu", "memory", "telemetry", "hardware", "disk space", "battery"]):
            plan.steps.append(
                PlanStep(
                    tool_name="system.telemetry",
                    arguments={},
                    description="Check system hardware and resource utilization",
                )
            )
            plan.state = TaskState.PENDING
            return plan

        # 3. Volume commands: "set volume to 50" / "volume"
        vol_match = re.search(r"set volume to (\d+)", lower_goal)
        if vol_match:
            level = int(vol_match.group(1))
            plan.steps.append(
                PlanStep(
                    tool_name="system.volume",
                    arguments={"level": level},
                    description=f"Set system volume to {level}%",
                )
            )
            plan.state = TaskState.PENDING
            return plan

        if "volume" in lower_goal and ("get" in lower_goal or "what" in lower_goal or "check" in lower_goal):
            plan.steps.append(
                PlanStep(
                    tool_name="system.volume",
                    arguments={},
                    description="Query current system volume",
                )
            )
            plan.state = TaskState.PENDING
            return plan

        # 4. Open Application: "open chrome", "launch notepad", "start vs code"
        open_match = re.search(r"(?:open|launch|start)\s+([a-zA-Z0-9\s_\-\.]+)", lower_goal)
        if open_match and not ("folder" in lower_goal or "file" in lower_goal):
            app_name = open_match.group(1).strip()
            # Clean up trailing words like "please" or "app"
            app_name = re.sub(r"\b(app|application|please)\b", "", app_name).strip()
            plan.steps.append(
                PlanStep(
                    tool_name="system.open_app",
                    arguments={"app_name": app_name},
                    description=f"Launch application '{app_name}'",
                )
            )
            plan.state = TaskState.PENDING
            return plan

        # 5. Close Application: "close chrome", "kill notepad"
        close_match = re.search(r"(?:close|kill|quit|terminate)\s+([a-zA-Z0-9\s_\-\.]+)", lower_goal)
        if close_match and not ("folder" in lower_goal or "file" in lower_goal):
            app_name = close_match.group(1).strip()
            app_name = re.sub(r"\b(app|application|please)\b", "", app_name).strip()
            plan.steps.append(
                PlanStep(
                    tool_name="system.close_app",
                    arguments={"app_name": app_name},
                    description=f"Close application '{app_name}'",
                )
            )
            plan.state = TaskState.PENDING
            return plan

        # 6. File Search: "find my machine learning project", "search for file X"
        if any(kw in lower_goal for kw in ["find", "search", "where is", "locate"]):
            # Extract query
            query = re.sub(r"^(?:hey\s+neron,?\s*)?(?:find|search(?:\s+for)?|where\s+is|locate)\s+", "", lower_goal).strip()
            plan.steps.append(
                PlanStep(
                    tool_name="filesystem.search",
                    arguments={"query": query},
                    description=f"Search filesystem for '{query}'",
                )
            )
            plan.state = TaskState.PENDING
            return plan

        # 7. Create Folder / File: "create a folder called Research"
        create_dir_match = re.search(r"create (?:a )?folder (?:called |named )?([a-zA-Z0-9_\-\.]+)", lower_goal)
        if create_dir_match:
            folder_name = create_dir_match.group(1).strip()
            plan.steps.append(
                PlanStep(
                    tool_name="terminal.execute",
                    arguments={"command": f"mkdir -p {folder_name}" if context.get("platform") != "windows" else f"New-Item -ItemType Directory -Force -Path '{folder_name}'"},
                    description=f"Create folder '{folder_name}'",
                )
            )
            plan.state = TaskState.PENDING
            return plan

        # 8. Terminal command: "run command X", "exec X"
        exec_match = re.search(r"(?:run|execute|exec)(?:\s+command)?\s+(.+)", clean_goal, re.IGNORECASE)
        if exec_match:
            cmd = exec_match.group(1).strip()
            plan.steps.append(
                PlanStep(
                    tool_name="terminal.execute",
                    arguments={"command": cmd},
                    description=f"Execute command: {cmd}",
                )
            )
            plan.state = TaskState.PENDING
            return plan

        # Fallback: Default to terminal or filesystem search depending on input
        plan.steps.append(
            PlanStep(
                tool_name="filesystem.search",
                arguments={"query": clean_goal},
                description=f"Search system matching '{clean_goal}'",
            )
        )
        plan.state = TaskState.PENDING
        return plan
