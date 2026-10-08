"""DAG-based execution engine with topological step resolution, verification, retry, and rollback."""

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
import time

from neron.core.events.bus import EventBus, get_default_bus
from neron.core.events.event import (
    EVENT_TASK_COMPLETED,
    EVENT_TASK_FAILED,
    EVENT_TASK_STATE_CHANGED,
    Event,
    TaskStateChangedEvent,
)
from neron.core.executor.failure_analyzer import analyze_failure
from neron.core.executor.verifier import verify_step
from neron.core.state.models import FailureAnalysis, PlanStep, StepFailureMode, TaskPlan, TaskState
from neron.security.emergency_stop import EmergencyStopCoordinator, EmergencyStopTriggered, get_emergency_stop
from neron.security.policy import PermissionDeniedError
from neron.tools.registry import ToolRegistry
from neron.utils.logger import get_logger

logger = get_logger("core.dag_executor")


class DAGExecutionError(Exception):
    """Raised when the DAG is malformed (cycles, missing deps)."""


class DAGExecutor:
    """
    Executes a TaskPlan whose steps form a Directed Acyclic Graph.

    Features:
    - Topological ordering with dependency resolution
    - Cycle detection
    - Post-step verification via Verifier
    - Typed failure analysis via FailureAnalyzer
    - Retry with exponential back-off
    - Rollback execution for failed steps
    - Optional steps (failure doesn't halt plan)
    - Emergency stop propagation at every decision point
    """

    RETRY_DELAYS = [0.5, 1.5, 3.0]   # seconds per retry attempt

    def __init__(
        self,
        tool_registry: ToolRegistry,
        event_bus: Optional[EventBus] = None,
        emergency_stop: Optional[EmergencyStopCoordinator] = None,
    ):
        self.tool_registry = tool_registry
        self.event_bus = event_bus or get_default_bus()
        self.emergency_stop = emergency_stop or get_emergency_stop()

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def execute_plan(self, plan: TaskPlan) -> TaskPlan:
        """Execute the plan's DAG, respecting dependencies. Returns the mutated plan."""
        logger.info(f"[DAG] Starting plan '{plan.task_id}': {plan.goal}")
        self._transition_plan(plan, TaskState.EXECUTING)

        try:
            ordered_steps = self._topological_sort(plan)
        except DAGExecutionError as e:
            self._transition_plan(plan, TaskState.FAILED, error=str(e))
            return plan

        for step in ordered_steps:
            # ── Check emergency stop ────────────────────────────────────────
            if self.emergency_stop.is_stopped():
                logger.warning(f"[DAG] Emergency stop — cancelling plan '{plan.task_id}'")
                step.state = TaskState.CANCELLED
                self._transition_plan(plan, TaskState.CANCELLED, error="Aborted by Emergency Stop")
                return plan

            # ── Skip steps whose dependencies failed ────────────────────────
            if not plan.is_step_ready(step):
                failed_deps = [
                    dep for dep in step.depends_on
                    if dep in plan.failed_step_ids
                ]
                if step.is_optional:
                    logger.info(f"[DAG] Optional step '{step.description}' skipped (dep failed: {failed_deps})")
                    step.state = TaskState.SKIPPED
                    plan.warnings.append(f"Optional step '{step.description}' skipped due to failed dependencies.")
                    continue
                else:
                    step.state = TaskState.FAILED
                    step.failure_analysis = FailureAnalysis(
                        mode=StepFailureMode.DEPENDENCY_FAILED,
                        is_retryable=False,
                        recovery_suggestion=f"Dependencies {failed_deps} must succeed before this step can run.",
                        raw_error=f"Dependencies not met: {failed_deps}",
                    )
                    step.error = step.failure_analysis.raw_error
                    self._transition_plan(plan, TaskState.FAILED, error=step.error)
                    return plan

            # ── Execute the step ────────────────────────────────────────────
            success = self._execute_step(plan, step)

            if not success and not step.is_optional:
                # Mark all downstream pending steps as blocked
                self._mark_remaining_failed(plan, ordered_steps, current_failed=step)
                # Attempt rollback if defined
                self._run_rollback(plan, step)
                self._transition_plan(plan, TaskState.FAILED, error=step.error)
                return plan
            elif not success and step.is_optional:
                plan.warnings.append(f"Optional step '{step.description}' failed and was skipped.")

        # ── All required steps done ─────────────────────────────────────────
        plan.completed_at = datetime.now(timezone.utc).isoformat()
        self._transition_plan(plan, TaskState.COMPLETED)
        logger.info(f"[DAG] Plan '{plan.task_id}' completed successfully.")
        return plan

    # ─────────────────────────────────────────────────────────────────────────
    # Step execution
    # ─────────────────────────────────────────────────────────────────────────

    def _execute_step(self, plan: TaskPlan, step: PlanStep) -> bool:
        """Run a single step with retry, verification, and failure analysis."""
        step_start = time.time()
        self._transition_step(step, TaskState.EXECUTING)

        attempt = 0
        while attempt <= step.max_retries:
            try:
                self.emergency_stop.assert_not_stopped()

                logger.info(f"[DAG] Running step '{step.description}' (attempt {attempt + 1}/{step.max_retries + 1})")

                tool_result = self.tool_registry.execute(
                    tool_name=step.tool_name,
                    arguments=step.arguments,
                    task_id=plan.task_id,
                    step_id=step.step_id,
                )

                step.duration_ms = (time.time() - step_start) * 1000

                if tool_result.success:
                    step.result = tool_result.output
                    # ── Verify ────────────────────────────────────────────
                    self._transition_step(step, TaskState.VERIFYING)
                    verification = verify_step(step, self.tool_registry)
                    step.verification = verification

                    if verification.passed:
                        self._transition_step(step, TaskState.COMPLETED)
                        logger.info(f"[DAG] Step '{step.description}' completed & verified.")
                        return True
                    else:
                        step.error = f"Verification failed: {verification.details}"
                        step.failure_analysis = analyze_failure(
                            step.error, step.tool_name, attempt, step.max_retries
                        )
                        logger.warning(f"[DAG] Verification failed for '{step.description}': {verification.details}")
                        # Verification failures are not retried
                        self._transition_step(step, TaskState.FAILED)
                        return False
                else:
                    raw_error = tool_result.error or "Tool returned failure."
                    step.error = raw_error
                    analysis = analyze_failure(raw_error, step.tool_name, attempt, step.max_retries)
                    step.failure_analysis = analysis
                    logger.warning(f"[DAG] Step '{step.description}' attempt {attempt + 1} failed: {raw_error}")

                    if not analysis.is_retryable:
                        self._transition_step(step, TaskState.FAILED)
                        return False

            except EmergencyStopTriggered as e:
                step.error = str(e)
                step.failure_analysis = analyze_failure(str(e), step.tool_name, attempt, step.max_retries)
                self._transition_step(step, TaskState.CANCELLED)
                return False

            except PermissionDeniedError as e:
                step.error = f"Permission Denied: {e}"
                step.failure_analysis = analyze_failure(step.error, step.tool_name, attempt, step.max_retries)
                logger.warning(f"[DAG] {step.error}")
                self._transition_step(step, TaskState.FAILED)
                return False

            except Exception as e:
                step.error = f"Unexpected error: {str(e)}"
                step.failure_analysis = analyze_failure(step.error, step.tool_name, attempt, step.max_retries)
                logger.error(f"[DAG] {step.error}", exc_info=True)

            # ── Retry delay ───────────────────────────────────────────────
            attempt += 1
            if attempt <= step.max_retries:
                delay = self.RETRY_DELAYS[min(attempt - 1, len(self.RETRY_DELAYS) - 1)]
                logger.info(f"[DAG] Retrying step '{step.description}' in {delay}s...")
                time.sleep(delay)

        step.retry_count = attempt - 1
        self._transition_step(step, TaskState.FAILED)
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Downstream failure propagation
    # ─────────────────────────────────────────────────────────────────────────

    def _mark_remaining_failed(
        self, plan: TaskPlan, ordered_steps: List[PlanStep], current_failed: PlanStep
    ) -> None:
        """Mark all PENDING steps that follow the failed step as DEPENDENCY_FAILED."""
        found = False
        for step in ordered_steps:
            if step is current_failed:
                found = True
                continue
            if found and step.state == TaskState.PENDING:
                step.state = TaskState.FAILED
                step.failure_analysis = FailureAnalysis(
                    mode=StepFailureMode.DEPENDENCY_FAILED,
                    is_retryable=False,
                    recovery_suggestion=f"Blocked by failure of '{current_failed.description}'.",
                    raw_error=f"Upstream step '{current_failed.step_id}' failed.",
                )
                step.error = step.failure_analysis.raw_error

    # ─────────────────────────────────────────────────────────────────────────
    # Rollback
    # ─────────────────────────────────────────────────────────────────────────

    def _run_rollback(self, plan: TaskPlan, failed_step: PlanStep) -> None:
        """Execute the rollback step for a failed step if defined."""
        if failed_step.rollback_step is None:
            return

        rb = failed_step.rollback_step
        logger.info(f"[DAG] Running rollback for failed step '{failed_step.description}': '{rb.description}'")
        plan.rollback_log.append(f"Rolling back '{failed_step.description}' via '{rb.description}'")

        try:
            rb_result = self.tool_registry.execute(
                tool_name=rb.tool_name,
                arguments=rb.arguments,
                task_id=plan.task_id,
                step_id=rb.step_id,
            )
            if rb_result.success:
                plan.rollback_log.append(f"Rollback '{rb.description}' succeeded.")
                logger.info(f"[DAG] Rollback succeeded for '{failed_step.description}'")
            else:
                plan.rollback_log.append(f"Rollback '{rb.description}' FAILED: {rb_result.error}")
                logger.error(f"[DAG] Rollback failed for '{failed_step.description}': {rb_result.error}")
        except Exception as e:
            plan.rollback_log.append(f"Rollback '{rb.description}' EXCEPTION: {e}")
            logger.error(f"[DAG] Rollback exception for '{failed_step.description}': {e}", exc_info=True)

    # ─────────────────────────────────────────────────────────────────────────
    # DAG topology
    # ─────────────────────────────────────────────────────────────────────────

    def _topological_sort(self, plan: TaskPlan) -> List[PlanStep]:
        """
        Kahn's algorithm topological sort on the step dependency graph.
        Raises DAGExecutionError on cycle detection or missing dependency.
        """
        step_map: Dict[str, PlanStep] = {s.step_id: s for s in plan.steps}

        # Validate all dependency references exist
        for step in plan.steps:
            for dep_id in step.depends_on:
                if dep_id not in step_map:
                    raise DAGExecutionError(
                        f"Step '{step.description}' depends on unknown step_id '{dep_id}'."
                    )

        # Build in-degree and adjacency
        in_degree: Dict[str, int] = defaultdict(int)
        adjacency: Dict[str, List[str]] = defaultdict(list)

        for step in plan.steps:
            in_degree.setdefault(step.step_id, 0)
            for dep_id in step.depends_on:
                adjacency[dep_id].append(step.step_id)
                in_degree[step.step_id] += 1

        # Kahn's BFS
        queue: deque = deque([s for s in plan.steps if in_degree[s.step_id] == 0])
        ordered: List[PlanStep] = []

        while queue:
            step = queue.popleft()
            ordered.append(step)
            for neighbor_id in adjacency[step.step_id]:
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    neighbor = step_map[neighbor_id]
                    queue.append(neighbor)

        if len(ordered) != len(plan.steps):
            raise DAGExecutionError(
                "Cycle detected in task plan DAG — circular dependencies are not allowed."
            )

        return ordered

    # ─────────────────────────────────────────────────────────────────────────
    # State transitions
    # ─────────────────────────────────────────────────────────────────────────

    def _transition_plan(self, plan: TaskPlan, new_state: TaskState, error: Optional[str] = None) -> None:
        old_state = plan.state
        plan.state = new_state
        if error:
            plan.error = error

        self.event_bus.publish(TaskStateChangedEvent(
            task_id=plan.task_id,
            old_state=old_state.value,
            new_state=new_state.value,
            details={"goal": plan.goal, "error": plan.error},
        ))

        if new_state == TaskState.COMPLETED:
            self.event_bus.publish(Event(
                event_type=EVENT_TASK_COMPLETED,
                payload={"task_id": plan.task_id, "goal": plan.goal},
            ))
        elif new_state in (TaskState.FAILED, TaskState.CANCELLED):
            self.event_bus.publish(Event(
                event_type=EVENT_TASK_FAILED,
                payload={
                    "task_id": plan.task_id,
                    "goal": plan.goal,
                    "state": new_state.value,
                    "error": plan.error,
                },
            ))

    def _transition_step(self, step: PlanStep, new_state: TaskState) -> None:
        step.state = new_state
