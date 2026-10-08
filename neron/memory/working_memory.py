"""In-memory active scratchpad and session context for Neron."""

import collections
import threading
import time
from typing import Any, Dict, List, Optional


class WorkingMemory:
    """
    Volatile in-memory store for active session state, variables, and recent turn history.
    """

    def __init__(self, max_history: int = 20):
        self._lock = threading.RLock()
        self.max_history = max_history
        self.session_id: str = f"session_{int(time.time())}"
        self.current_goal: Optional[str] = None
        self.active_plan_id: Optional[str] = None
        self.variables: Dict[str, Any] = {}
        self.history: collections.deque = collections.deque(maxlen=max_history)

    def set_goal(self, goal: Optional[str], plan_id: Optional[str] = None) -> None:
        with self._lock:
            self.current_goal = goal
            self.active_plan_id = plan_id

    def set_variable(self, key: str, value: Any) -> None:
        """Store a context variable (e.g. 'last_screenshot', 'selected_file')."""
        with self._lock:
            self.variables[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self.variables.get(key, default)

    def delete_variable(self, key: str) -> bool:
        with self._lock:
            if key in self.variables:
                del self.variables[key]
                return True
            return False

    def add_turn(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record turn into recent memory buffer."""
        with self._lock:
            self.history.append({
                "role": role,
                "content": content,
                "metadata": metadata or {},
                "timestamp": time.time(),
            })

    def get_recent_history(self, count: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self.history)
            if count is not None and count < len(items):
                return items[-count:]
            return items

    def clear(self) -> None:
        """Reset working state while preserving session ID."""
        with self._lock:
            self.current_goal = None
            self.active_plan_id = None
            self.variables.clear()
            self.history.clear()
