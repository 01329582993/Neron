"""Persistent security audit ledger for recording all capability and tool executions."""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from neron.utils.logger import get_logger, sanitize_message

logger = get_logger("audit")


class AuditLedger:
    """Thread-safe SQLite-backed audit recorder."""

    def __init__(self, db_path: str = "data/audit.db"):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database directory and schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    task_id TEXT,
                    step_id TEXT,
                    tool_name TEXT NOT NULL,
                    capabilities TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    arguments_json TEXT,
                    result_summary TEXT,
                    duration_ms REAL,
                    success INTEGER NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_events(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_tool ON audit_events(tool_name)")
            conn.commit()

    def record_event(
        self,
        tool_name: str,
        capabilities: List[str],
        decision: str,
        success: bool,
        task_id: Optional[str] = None,
        step_id: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
        result_summary: Optional[str] = None,
        duration_ms: float = 0.0,
    ) -> int:
        """Record a single tool or security event into the audit trail."""
        timestamp = datetime.now(timezone.utc).isoformat()
        capabilities_str = ",".join(capabilities)
        
        args_str = ""
        if arguments:
            try:
                args_str = sanitize_message(json.dumps(arguments, default=str))
            except Exception:
                args_str = "[Serialization Error]"

        sanitized_summary = sanitize_message(result_summary or "")

        with self._lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_events (
                    timestamp, task_id, step_id, tool_name, capabilities,
                    decision, arguments_json, result_summary, duration_ms, success
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                task_id or "",
                step_id or "",
                tool_name,
                capabilities_str,
                decision,
                args_str,
                sanitized_summary,
                duration_ms,
                1 if success else 0,
            ))
            conn.commit()
            return cursor.lastrowid or 0

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch the most recent audit records."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, timestamp, task_id, step_id, tool_name, capabilities,
                       decision, arguments_json, result_summary, duration_ms, success
                FROM audit_events
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
