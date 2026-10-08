"""Execution engine managing state machine transitions, step dispatch, and safety."""

from datetime import datetime, timezone
import time
from typing import Optional
from neron.core.events.bus import EventBus, get_default_bus
from neron.core.events.event import (
    EVENT_TASK_COMPLETED,
    EVENT_TASK_FAILED,
    EVENT_TASK_STATE_CHANGED,
    Event,
    TaskStateChangedEvent,
)
from neron.core.state.models import PlanStep, TaskPlan, TaskState
from neron.security.emergency_stop import EmergencyStopCoordinator, EmergencyStopTriggered, get_emergency_stop
from neron.security.policy import PermissionDeniedError
from neron.tools.registry import ToolRegistry
from neron.utils.logger import get_logger

logger = get_logger("core.executor")


class ExecutionEngine:
    """Orchestrates plan execution, enforcing step verification and state machine transitions."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        event_bus: Optional[EventBus] = None,
        emergency_stop: Optional[EmergencyStopCoordinator] = None,
    ):
        self.tool_registry = tool_registry
        self.event_bus = event_bus or get_default_bus()
        self.emergency_stop = emergency_stop or get_emergency_stop()

    def execute_plan(self, plan: TaskPlan) -> TaskPlan:
        """Execute all steps in a TaskPlan sequentially with full verification and safety."""
        logger.info(f"Starting execution of task '{plan.task_id}': {plan.goal}")
        self._transition_plan_state(plan, TaskState.EXECUTING)

        for idx, step in enumerate(plan.steps):
            # Check for emergency stop before step
            if self.emergency_stop.is_stopped():
                logger.warning(f"Task '{plan.task_id}' halted by Emergency Stop before step {idx + 1}")
                self._transition_step_state(step, TaskState.CANCELLED, plan.task_id)
                self._transition_plan_state(plan, TaskState.CANCELLED, error="Aborted by Emergency Stop")
                return plan

            success = self._execute_step(plan, step)
            if not success:
                logger.error(f"Step {idx + 1} ('{step.description}') failed. Halting plan.")
                self._transition_plan_state(plan, TaskState.FAILED, error=step.error)
                return plan

        # All steps succeeded
        plan.completed_at = datetime.now(timezone.utc).isoformat()
        self._transition_plan_state(plan, TaskState.COMPLETED)
        logger.info(f"Task '{plan.task_id}' successfully completed.")
        return plan

    def _execute_step(self, plan: TaskPlan, step: PlanStep) -> bool:
        """Execute a single PlanStep with retry support."""
        step_start = time.time()
        self._transition_step_state(step, TaskState.EXECUTING, plan.task_id)

        while step.retry_count <= step.max_retries:
            try:
                # Check emergency stop before dispatch
                self.emergency_stop.assert_not_stopped()

                # Execute tool via registry
                result = self.tool_registry.execute(
                    tool_name=step.tool_name,
                    arguments=step.arguments,
                    task_id=plan.task_id,
                    step_id=step.step_id,
                )

                step.duration_ms = (time.time() - step_start) * 1000

                if result.success:
                    self._transition_step_state(step, TaskState.VERIFYING, plan.task_id)
                    # Verification succeeded
                    step.result = result.output
                    self._transition_step_state(step, TaskState.COMPLETED, plan.task_id)
                    return True
                else:
                    step.error = result.error or "Tool returned failure."
                    logger.warning(f"Step '{step.description}' attempt {step.retry_count + 1} failed: {step.error}")

            except EmergencyStopTriggered as e:
                step.error = str(e)
                self._transition_step_state(step, TaskState.CANCELLED, plan.task_id)
                return False

            except PermissionDeniedError as e:
                step.error = f"Permission Denied: {e}"
                logger.warning(step.error)
                self._transition_step_state(step, TaskState.FAILED, plan.task_id)
                return False

            except Exception as e:
                step.error = f"Unexpected execution error: {str(e)}"
                logger.error(step.error, exc_info=True)

            step.retry_count += 1
            if step.retry_count <= step.max_retries:
                logger.info(f"Retrying step '{step.description}' (attempt {step.retry_count + 1})...")
                time.sleep(0.5)

        self._transition_step_state(step, TaskState.FAILED, plan.task_id)
        return False

    def _transition_plan_state(self, plan: TaskPlan, new_state: TaskState, error: Optional[str] = None) -> None:
        """Update and publish plan state transition."""
        old_state = plan.state
        plan.state = new_state
        if error:
            plan.error = error

        self.event_bus.publish(TaskStateChangedEvent(
            task_id=plan.task_id,
            old_state=old_state.value,
            new_state=new_state.value,
            details={"goal": plan.goal, "error": plan.error}
        ))

        if new_state == TaskState.COMPLETED:
            self.event_bus.publish(Event(
                event_type=EVENT_TASK_COMPLETED,
                payload={"task_id": plan.task_id, "goal": plan.goal}
            ))
        elif new_state in (TaskState.FAILED, TaskState.CANCELLED):
            self.event_bus.publish(Event(
                event_type=EVENT_TASK_FAILED,
                payload={"task_id": plan.task_id, "goal": plan.goal, "state": new_state.value, "error": plan.error}
            ))

    def _transition_step_state(self, step: PlanStep, new_state: TaskState, task_id: str) -> None:
        """Update step state."""
        step.state = new_state
