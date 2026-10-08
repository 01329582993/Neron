"""Task state machine and planning data models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
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


@dataclass
class PlanStep:
    """Individual atomic step within an overall task plan."""
    tool_name: str
    arguments: Dict[str, Any]
    description: str
    step_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    state: TaskState = TaskState.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 1
    duration_ms: float = 0.0

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
        }


@dataclass
class TaskPlan:
    """Structured plan containing one or more ordered steps to accomplish a user goal."""
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    state: TaskState = TaskState.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    error: Optional[str] = None

    @property
    def current_step(self) -> Optional[PlanStep]:
        for step in self.steps:
            if step.state in (TaskState.PENDING, TaskState.EXECUTING, TaskState.WAITING_FOR_PERMISSION):
                return step
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "state": self.state.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "steps": [s.to_dict() for s in self.steps],
        }
