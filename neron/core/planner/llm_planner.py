"""AI-driven task planner with automated offline heuristic fallback."""

import json
import re
from typing import Any, Dict, List, Optional
from neron.ai.base import LLMMessage, LLMProvider
from neron.ai.routing.router import AIRouter
from neron.core.planner.base import BasePlanner, HeuristicPlanner
from neron.core.state.models import PlanStep, TaskPlan, TaskState
from neron.tools.base import BaseTool
from neron.utils.logger import get_logger

logger = get_logger("core.planner.llm")


SYSTEM_PLANNER_PROMPT = """You are NERON, an advanced local-first desktop operating agent.
Your mission is to understand user intent and break it down into a structured sequence of executable tool steps.

Rules:
1. Always select from the provided tools.
2. For each action, supply the required arguments matching the tool schema.
3. Keep plans minimal, safe, and deterministic.
4. If the user asks a question that does not require system modifications, use read-only inspection tools (e.g. system.telemetry or filesystem.search).
"""


class LLMPlanner(BasePlanner):
    """Decomposes goals using an AI model with graceful heuristic fallback."""

    def __init__(
        self,
        ai_router: Optional[AIRouter] = None,
        fallback_planner: Optional[BasePlanner] = None,
    ):
        self.ai_router = ai_router or AIRouter()
        self.fallback_planner = fallback_planner or HeuristicPlanner()

    def plan(
        self,
        goal: str,
        context: Dict[str, Any],
        available_tools: List[BaseTool]
    ) -> TaskPlan:
        provider = self.ai_router.get_active_provider()

        # If active provider is heuristic, use HeuristicPlanner directly
        if provider.name == "heuristic":
            logger.debug("Active AI provider is heuristic; using HeuristicPlanner.")
            return self.fallback_planner.plan(goal, context, available_tools)

        logger.info(f"Generating plan via AI provider '{provider.name}' for goal: '{goal}'")
        tool_schemas = [t.to_llm_tool_definition() for t in available_tools]

        messages = [
            LLMMessage(role="system", content=SYSTEM_PLANNER_PROMPT),
            LLMMessage(
                role="user",
                content=(
                    f"User Request: {goal}\n"
                    f"System Platform: {context.get('platform')}\n"
                    f"Current Directory: {context.get('cwd')}\n"
                    f"Active Window: {context.get('active_window')}\n\n"
                    "Select the exact tools needed to fulfill this request."
                )
            )
        ]

        try:
            response = provider.chat(messages, tools=tool_schemas)

            # 1. Check for native tool calls
            if response.tool_calls:
                plan = TaskPlan(goal=goal, state=TaskState.PENDING)
                for tc in response.tool_calls:
                    plan.steps.append(
                        PlanStep(
                            tool_name=tc.name,
                            arguments=tc.arguments,
                            description=f"AI planned step: {tc.name}",
                        )
                    )
                logger.info(f"AI generated {len(plan.steps)} step(s) via tool-calling.")
                return plan

            # 2. Check if model returned JSON in content
            parsed_steps = self._try_parse_steps_from_text(response.content, available_tools)
            if parsed_steps:
                plan = TaskPlan(goal=goal, steps=parsed_steps, state=TaskState.PENDING)
                logger.info(f"AI generated {len(plan.steps)} step(s) from structured text.")
                return plan

        except Exception as e:
            logger.warning(f"AI provider '{provider.name}' planning failed ({e}). Falling back to heuristic planner.")

        # Fallback to deterministic heuristic planner
        return self.fallback_planner.plan(goal, context, available_tools)

    def _try_parse_steps_from_text(self, text: str, available_tools: List[BaseTool]) -> List[PlanStep]:
        """Attempt to extract structured steps from markdown/JSON text."""
        valid_tool_names = {t.name for t in available_tools}
        json_match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
        if not json_match:
            return []

        try:
            data = json.loads(json_match.group(0))
            steps = []
            for item in data:
                tool_name = item.get("tool") or item.get("tool_name")
                if tool_name in valid_tool_names:
                    steps.append(
                        PlanStep(
                            tool_name=tool_name,
                            arguments=item.get("arguments", {}),
                            description=item.get("description", f"Step: {tool_name}")
                        )
                    )
            return steps
        except Exception:
            return []
