"""Task state machine and planning data models — with DAG dependency support."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import uuid


class TaskState(Enum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    WAITING_FOR_PERMISSION = "WAITING_FOR_PERMISSION"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class StepFailureMode(Enum):
    """Classification of why a step failed — guides recovery strategy."""
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    TIMEOUT = "TIMEOUT"
    TOOL_RUNTIME_ERROR = "TOOL_RUNTIME_ERROR"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    DEPENDENCY_FAILED = "DEPENDENCY_FAILED"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    UNKNOWN = "UNKNOWN"


@dataclass
class VerificationResult:
    """Result of a post-step verification check."""
    passed: bool
    details: str = ""
    expected: Optional[str] = None
    actual: Optional[str] = None


@dataclass
class FailureAnalysis:
    """Structured analysis of why a step failed and what to do about it."""
    mode: StepFailureMode = StepFailureMode.UNKNOWN
    is_retryable: bool = False
    recovery_suggestion: str = ""
    raw_error: str = ""


@dataclass
class PlanStep:
    """Individual atomic step within an overall task plan — supports DAG dependencies."""
    tool_name: str
    arguments: Dict[str, Any]
    description: str
    step_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    state: TaskState = TaskState.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2
    duration_ms: float = 0.0

    # DAG fields
    depends_on: List[str] = field(default_factory=list)   # step_ids this step waits for
    is_optional: bool = False                              # if True, failure won't halt plan
    rollback_step: Optional["PlanStep"] = None             # compensating action on failure

    # Verification
    verification: Optional[VerificationResult] = None
    failure_analysis: Optional[FailureAnalysis] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "description": self.description,
            "arguments": self.arguments,
            "state": self.state.value,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "duration_ms": self.duration_ms,
            "depends_on": self.depends_on,
            "is_optional": self.is_optional,
            "verification": {
                "passed": self.verification.passed,
                "details": self.verification.details,
            } if self.verification else None,
            "failure_analysis": {
                "mode": self.failure_analysis.mode.value,
                "recovery_suggestion": self.failure_analysis.recovery_suggestion,
            } if self.failure_analysis else None,
        }


@dataclass
class TaskPlan:
    """Structured plan containing one or more steps — organized as a DAG."""
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    state: TaskState = TaskState.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    error: Optional[str] = None

    # Execution tracking
    rollback_log: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def current_step(self) -> Optional[PlanStep]:
        for step in self.steps:
            if step.state in (TaskState.PENDING, TaskState.EXECUTING, TaskState.WAITING_FOR_PERMISSION):
                return step
        return None

    @property
    def completed_step_ids(self) -> Set[str]:
        return {s.step_id for s in self.steps if s.state == TaskState.COMPLETED}

    @property
    def failed_step_ids(self) -> Set[str]:
        return {s.step_id for s in self.steps if s.state == TaskState.FAILED}

    def get_step_by_id(self, step_id: str) -> Optional[PlanStep]:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def is_step_ready(self, step: PlanStep) -> bool:
        """Check if all dependencies for this step are satisfied."""
        completed = self.completed_step_ids
        return all(dep_id in completed for dep_id in step.depends_on)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "state": self.state.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "warnings": self.warnings,
            "rollback_log": self.rollback_log,
            "steps": [s.to_dict() for s in self.steps],
        }
