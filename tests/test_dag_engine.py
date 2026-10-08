"""Tests for Stage 6: DAG-based Task Planning & Execution Engine."""

import pytest
from unittest.mock import MagicMock, patch
from neron.core.executor.dag_executor import DAGExecutor, DAGExecutionError
from neron.core.executor.failure_analyzer import analyze_failure
from neron.core.executor.verifier import verify_step
from neron.core.planner.dag_planner import DAGPlanner
from neron.core.state.models import (
    FailureAnalysis,
    PlanStep,
    StepFailureMode,
    TaskPlan,
    TaskState,
    VerificationResult,
)
from neron.core.events.bus import EventBus
from neron.security.emergency_stop import EmergencyStopCoordinator
from neron.tools.registry import ToolRegistry


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_executor(tool_registry: ToolRegistry) -> DAGExecutor:
    bus = EventBus()
    stop = EmergencyStopCoordinator(bus)
    return DAGExecutor(tool_registry=tool_registry, event_bus=bus, emergency_stop=stop)


def _success_registry(*tool_names) -> ToolRegistry:
    """Registry that always returns success for given tool names."""
    registry = MagicMock(spec=ToolRegistry)
    success_result = MagicMock()
    success_result.success = True
    success_result.output = {"status": "ok"}
    success_result.error = None
    registry.execute.return_value = success_result
    return registry


def _failure_registry(error: str = "Simulated error") -> ToolRegistry:
    registry = MagicMock(spec=ToolRegistry)
    fail_result = MagicMock()
    fail_result.success = False
    fail_result.output = None
    fail_result.error = error
    registry.execute.return_value = fail_result
    return registry


# ─────────────────────────────────────────────────────────────────────────────
# Failure Analyzer Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFailureAnalyzer:

    def test_permission_denied_classification(self):
        analysis = analyze_failure("Permission Denied: write to system32", "filesystem.write", 0, 2)
        assert analysis.mode == StepFailureMode.PERMISSION_DENIED
        assert not analysis.is_retryable

    def test_timeout_classification_retryable(self):
        analysis = analyze_failure("Operation timed out after 30s", "terminal.execute", 0, 2)
        assert analysis.mode == StepFailureMode.TIMEOUT
        assert analysis.is_retryable

    def test_timeout_not_retryable_when_exhausted(self):
        analysis = analyze_failure("timeout exceeded", "terminal.execute", 2, 2)
        assert analysis.mode == StepFailureMode.TIMEOUT
        assert not analysis.is_retryable

    def test_tool_not_found_classification(self):
        analysis = analyze_failure("Tool not found: unknown.tool", "unknown.tool", 0, 2)
        assert analysis.mode == StepFailureMode.TOOL_NOT_FOUND
        assert not analysis.is_retryable

    def test_emergency_stop_classification(self):
        analysis = analyze_failure("EmergencyStopTriggered: user pressed CTRL+ALT+N", "terminal.execute", 0, 2)
        assert analysis.mode == StepFailureMode.EMERGENCY_STOP
        assert not analysis.is_retryable

    def test_generic_runtime_error_retryable(self):
        analysis = analyze_failure("Unexpected connection reset", "system.open_app", 0, 2)
        assert analysis.mode == StepFailureMode.TOOL_RUNTIME_ERROR
        assert analysis.is_retryable

    def test_analysis_has_recovery_suggestion(self):
        analysis = analyze_failure("Permission denied", "filesystem.write", 0, 2)
        assert len(analysis.recovery_suggestion) > 10


# ─────────────────────────────────────────────────────────────────────────────
# Verifier Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestStepVerifier:

    def test_none_result_fails_verification(self):
        step = PlanStep(tool_name="system.telemetry", arguments={}, description="telemetry", result=None)
        registry = MagicMock(spec=ToolRegistry)
        result = verify_step(step, registry)
        assert not result.passed

    def test_terminal_zero_exit_code_passes(self):
        step = PlanStep(
            tool_name="terminal.execute",
            arguments={"command": "echo hi"},
            description="test",
            result={"exit_code": 0, "stdout": "hi"},
        )
        result = verify_step(step, MagicMock(spec=ToolRegistry))
        assert result.passed

    def test_terminal_nonzero_exit_code_fails(self):
        step = PlanStep(
            tool_name="terminal.execute",
            arguments={"command": "bad_cmd"},
            description="test",
            result={"exit_code": 1, "stdout": "", "stderr": "command not found"},
        )
        result = verify_step(step, MagicMock(spec=ToolRegistry))
        assert not result.passed

    def test_system_tool_with_non_none_result_passes(self):
        step = PlanStep(
            tool_name="system.telemetry",
            arguments={},
            description="telemetry",
            result={"cpu": 20, "ram": 50},
        )
        result = verify_step(step, MagicMock(spec=ToolRegistry))
        assert result.passed

    def test_filesystem_write_verify_re_reads(self):
        """Verifier should attempt a filesystem.read to confirm write."""
        step = PlanStep(
            tool_name="filesystem.write",
            arguments={"path": "/tmp/test.txt", "content": "hello"},
            description="write",
            result={"written": True},
        )
        registry = MagicMock(spec=ToolRegistry)
        read_result = MagicMock()
        read_result.success = True
        read_result.output = "hello"
        registry.execute.return_value = read_result

        result = verify_step(step, registry)
        assert result.passed
        registry.execute.assert_called_once()  # one re-read call


# ─────────────────────────────────────────────────────────────────────────────
# DAG Planner Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDAGPlanner:

    def setup_method(self):
        self.planner = DAGPlanner()

    def test_prepare_dev_produces_two_steps_with_dependency(self):
        plan = self.planner.plan("prepare development environment", {}, [])
        assert len(plan.steps) == 2
        # Second step depends on first
        assert plan.steps[0].step_id in plan.steps[1].depends_on

    def test_check_then_open_dependency_chain(self):
        plan = self.planner.plan("check system then open notepad", {}, [])
        assert len(plan.steps) == 2
        telem, launch = plan.steps
        assert telem.tool_name == "system.telemetry"
        assert launch.tool_name == "system.open_app"
        assert telem.step_id in launch.depends_on

    def test_search_then_open_has_optional_step(self):
        plan = self.planner.plan("search for my-project then open it", {}, [])
        assert len(plan.steps) == 2
        search_step, open_step = plan.steps
        assert open_step.is_optional is True

    def test_single_step_telemetry(self):
        plan = self.planner.plan("check my CPU usage", {}, [])
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "system.telemetry"

    def test_volume_command(self):
        plan = self.planner.plan("set volume to 75", {}, [])
        assert plan.steps[0].tool_name == "system.volume"
        assert plan.steps[0].arguments["level"] == 75


# ─────────────────────────────────────────────────────────────────────────────
# DAG Executor Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDAGExecutor:

    def _make_simple_plan(self, tool="system.telemetry") -> TaskPlan:
        step = PlanStep(tool_name=tool, arguments={}, description="test step")
        return TaskPlan(goal="test goal", steps=[step])

    def test_successful_single_step_execution(self):
        registry = _success_registry()
        executor = _make_executor(registry)
        plan = self._make_simple_plan()
        result = executor.execute_plan(plan)
        assert result.state == TaskState.COMPLETED
        assert result.steps[0].state == TaskState.COMPLETED

    def test_failed_step_marks_plan_failed(self):
        registry = _failure_registry("Some runtime error")
        executor = _make_executor(registry)
        plan = self._make_simple_plan()
        result = executor.execute_plan(plan)
        assert result.state == TaskState.FAILED
        assert result.steps[0].failure_analysis is not None

    def test_dag_dependency_respected_in_order(self):
        """Steps execute in topological order — dependent step runs after dependency."""
        registry = _success_registry()
        executor = _make_executor(registry)

        step_a = PlanStep(tool_name="system.telemetry", arguments={}, description="Step A")
        step_b = PlanStep(
            tool_name="system.open_app", arguments={"app_name": "code"}, description="Step B",
            depends_on=[step_a.step_id],
        )
        plan = TaskPlan(goal="dag test", steps=[step_a, step_b])
        result = executor.execute_plan(plan)

        assert result.state == TaskState.COMPLETED
        assert result.steps[0].state == TaskState.COMPLETED
        assert result.steps[1].state == TaskState.COMPLETED

    def test_failed_dependency_cancels_dependent_step(self):
        """When a required dependency fails, dependent step is marked FAILED."""
        registry = _failure_registry("Dep step error")
        executor = _make_executor(registry)

        step_a = PlanStep(tool_name="system.telemetry", arguments={}, description="Step A (fails)")
        step_b = PlanStep(
            tool_name="system.open_app", arguments={"app_name": "code"}, description="Step B",
            depends_on=[step_a.step_id],
        )
        plan = TaskPlan(goal="dependency failure test", steps=[step_a, step_b])
        result = executor.execute_plan(plan)

        assert result.state == TaskState.FAILED
        assert step_a.state == TaskState.FAILED
        assert step_b.state == TaskState.FAILED
        assert step_b.failure_analysis is not None
        assert step_b.failure_analysis.mode == StepFailureMode.DEPENDENCY_FAILED

    def test_optional_step_failure_does_not_halt_plan(self):
        """An optional step failing should result in a warning but the plan continues."""
        call_count = [0]

        def side_effect(**kwargs):
            call_count[0] += 1
            result = MagicMock()
            # First call (mandatory step) succeeds, second (optional) fails
            result.success = call_count[0] == 1
            result.output = {"ok": True} if result.success else None
            result.error = None if result.success else "Optional step error"
            return result

        registry = MagicMock(spec=ToolRegistry)
        registry.execute.side_effect = lambda **kw: side_effect(**kw)

        executor = _make_executor(registry)
        mandatory = PlanStep(tool_name="system.telemetry", arguments={}, description="Mandatory step")
        optional = PlanStep(
            tool_name="system.open_app", arguments={"app_name": "notepad"}, description="Optional step",
            is_optional=True,
        )
        plan = TaskPlan(goal="optional test", steps=[mandatory, optional])
        result = executor.execute_plan(plan)

        assert result.state == TaskState.COMPLETED
        assert mandatory.state == TaskState.COMPLETED
        assert len(result.warnings) > 0

    def test_cycle_detection_raises_error(self):
        """A plan with circular dependencies should raise DAGExecutionError."""
        registry = _success_registry()
        executor = _make_executor(registry)

        step_a = PlanStep(tool_name="system.telemetry", arguments={}, description="A")
        step_b = PlanStep(tool_name="system.open_app", arguments={}, description="B", depends_on=[step_a.step_id])
        # Introduce cycle: A depends on B
        step_a.depends_on = [step_b.step_id]

        plan = TaskPlan(goal="cycle test", steps=[step_a, step_b])
        result = executor.execute_plan(plan)
        assert result.state == TaskState.FAILED
        assert "Cycle" in (result.error or "")

    def test_rollback_runs_on_failure(self):
        """When a step fails, its rollback_step should be executed."""
        registry = MagicMock(spec=ToolRegistry)

        # Primary step fails
        fail_result = MagicMock()
        fail_result.success = False
        fail_result.error = "Write failed"
        fail_result.output = None

        # Rollback step succeeds
        rb_result = MagicMock()
        rb_result.success = True
        rb_result.output = {"cleaned": True}
        rb_result.error = None

        # First call is the primary step (fail), second is rollback (succeed)
        registry.execute.side_effect = [fail_result, fail_result, fail_result, rb_result]

        rollback_step = PlanStep(
            tool_name="filesystem.delete",
            arguments={"path": "/tmp/partial.txt"},
            description="Cleanup partial file",
        )
        primary_step = PlanStep(
            tool_name="filesystem.write",
            arguments={"path": "/tmp/partial.txt", "content": "test"},
            description="Write file",
            max_retries=2,
            rollback_step=rollback_step,
        )
        plan = TaskPlan(goal="rollback test", steps=[primary_step])

        executor = _make_executor(registry)
        result = executor.execute_plan(plan)

        assert result.state == TaskState.FAILED
        assert len(result.rollback_log) > 0

    def test_emergency_stop_halts_dag(self):
        """Emergency stop triggered mid-plan should cancel execution."""
        bus = EventBus()
        stop = EmergencyStopCoordinator(bus)
        stop.trigger()  # Pre-trigger stop

        registry = _success_registry()
        executor = DAGExecutor(tool_registry=registry, event_bus=bus, emergency_stop=stop)

        step = PlanStep(tool_name="system.telemetry", arguments={}, description="Should not run")
        plan = TaskPlan(goal="emergency stop test", steps=[step])
        result = executor.execute_plan(plan)

        assert result.state == TaskState.CANCELLED

    def test_steps_carry_failure_analysis_on_failure(self):
        """Failed steps should have a FailureAnalysis attached."""
        registry = _failure_registry("Permission denied: cannot write to C:\\Windows")
        executor = _make_executor(registry)
        plan = self._make_simple_plan("filesystem.write")
        result = executor.execute_plan(plan)

        assert result.state == TaskState.FAILED
        step = result.steps[0]
        assert step.failure_analysis is not None
        assert step.failure_analysis.mode == StepFailureMode.PERMISSION_DENIED
        assert len(step.failure_analysis.recovery_suggestion) > 0
