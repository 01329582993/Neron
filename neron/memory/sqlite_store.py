"""SQLite-backed structured persistent memory store for Neron."""

import json
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from neron.utils.logger import get_logger

logger = get_logger("memory.sqlite")


class SQLiteMemoryStore:
    """
    Thread-safe persistent SQLite storage for facts, conversation turns, and procedural recipes.
    """

    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            default_dir = Path.home() / ".neron" / "memory"
            default_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(default_dir / "neron_memory.db")
        else:
            p = Path(db_path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            self.db_path = str(p)

        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def close(self) -> None:
        """Close any lingering resources if needed."""
        pass

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()

                # 1. Facts table (user preferences, environment notes, system properties)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS facts (
                        category TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        confidence REAL DEFAULT 1.0,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        PRIMARY KEY (category, key)
                    )
                """)

                # 2. Conversation history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_turns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata_json TEXT DEFAULT '{}',
                        timestamp REAL NOT NULL
                    )
                """)

                # 3. Procedural recipes table (reusable automated multi-step plans)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS recipes (
                        name TEXT PRIMARY KEY,
                        goal_pattern TEXT NOT NULL,
                        steps_json TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        usage_count INTEGER DEFAULT 0,
                        last_used_at REAL DEFAULT 0.0
                    )
                """)

                # 4. FTS5 Virtual Table for full-text searching across facts
                try:
                    cursor.execute("""
                        CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
                            category,
                            key,
                            value,
                            content='facts',
                            content_rowid='rowid'
                        )
                    """)
                except Exception:
                    logger.warning("FTS5 full-text extension not available; falling back to LIKE queries.")

                conn.commit()
            finally:
                conn.close()

    # ── Fact Operations ────────────────────────────────────────────────────────

    def store_fact(
        self,
        key: str,
        value: Any,
        category: str = "general",
        confidence: float = 1.0,
    ) -> None:
        """Store or update a persistent fact."""
        now = time.time()
        val_str = json.dumps(value) if not isinstance(value, str) else value

        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO facts (category, key, value, confidence, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(category, key) DO UPDATE SET
                        value = excluded.value,
                        confidence = excluded.confidence,
                        updated_at = excluded.updated_at
                """, (category, key, val_str, confidence, now, now))

                # Sync FTS if present
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO facts_fts (rowid, category, key, value)
                        VALUES (
                            (SELECT rowid FROM facts WHERE category = ? AND key = ?),
                            ?, ?, ?
                        )
                    """, (category, key, category, key, val_str))
                except Exception:
                    pass

                conn.commit()
                logger.debug(f"Stored fact [{category}] {key}")
            finally:
                conn.close()

    def get_fact(self, key: str, category: Optional[str] = None) -> Optional[Any]:
        """Retrieve a specific fact by key and optional category."""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                if category:
                    cursor.execute(
                        "SELECT value FROM facts WHERE category = ? AND key = ?",
                        (category, key),
                    )
                else:
                    cursor.execute(
                        "SELECT value FROM facts WHERE key = ? ORDER BY updated_at DESC LIMIT 1",
                        (key,),
                    )
                row = cursor.fetchone()
                if not row:
                    return None
                val_str = row["value"]
                try:
                    return json.loads(val_str)
                except Exception:
                    return val_str
            finally:
                conn.close()

    def delete_fact(self, key: str, category: Optional[str] = None) -> bool:
        """Delete a fact by key."""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                if category:
                    cursor.execute(
                        "DELETE FROM facts WHERE category = ? AND key = ?",
                        (category, key),
                    )
                else:
                    cursor.execute("DELETE FROM facts WHERE key = ?", (key,))
                deleted = cursor.rowcount > 0
                conn.commit()
                return deleted
            finally:
                conn.close()

    def list_facts(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all facts, optionally filtered by category."""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                if category:
                    cursor.execute(
                        "SELECT category, key, value, confidence, updated_at FROM facts WHERE category = ? ORDER BY key",
                        (category,),
                    )
                else:
                    cursor.execute(
                        "SELECT category, key, value, confidence, updated_at FROM facts ORDER BY category, key"
                    )
                rows = cursor.fetchall()

                results = []
                for r in rows:
                    val = r["value"]
                    try:
                        parsed_val = json.loads(val)
                    except Exception:
                        parsed_val = val
                    results.append({
                        "category": r["category"],
                        "key": r["key"],
                        "value": parsed_val,
                        "confidence": r["confidence"],
                        "updated_at": r["updated_at"],
                    })
                return results
            finally:
                conn.close()

    def search_facts(self, query: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Full-text or substring search over stored facts."""
        clean = query.strip()
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()

                # Attempt FTS query first
                try:
                    fts_query = f"{clean}*"
                    if category:
                        cursor.execute("""
                            SELECT f.category, f.key, f.value, f.confidence, f.updated_at
                            FROM facts f
                            JOIN facts_fts fts ON f.rowid = fts.rowid
                            WHERE fts MATCH ? AND f.category = ?
                            ORDER BY f.updated_at DESC
                        """, (fts_query, category))
                    else:
                        cursor.execute("""
                            SELECT f.category, f.key, f.value, f.confidence, f.updated_at
                            FROM facts f
                            JOIN facts_fts fts ON f.rowid = fts.rowid
                            WHERE fts MATCH ?
                            ORDER BY f.updated_at DESC
                        """, (fts_query,))
                    rows = cursor.fetchall()
                    if rows:
                        return [self._format_fact_row(r) for r in rows]
                except Exception:
                    pass

                # Fallback to standard LIKE matching
                pattern = f"%{clean}%"
                if category:
                    cursor.execute("""
                        SELECT category, key, value, confidence, updated_at
                        FROM facts
                        WHERE (key LIKE ? OR value LIKE ?) AND category = ?
                        ORDER BY updated_at DESC
                    """, (pattern, pattern, category))
                else:
                    cursor.execute("""
                        SELECT category, key, value, confidence, updated_at
                        FROM facts
                        WHERE key LIKE ? OR value LIKE ?
                        ORDER BY updated_at DESC
                    """, (pattern, pattern))

                rows = cursor.fetchall()
                return [self._format_fact_row(r) for r in rows]
            finally:
                conn.close()

    def _format_fact_row(self, r: sqlite3.Row) -> Dict[str, Any]:
        val = r["value"]
        try:
            parsed = json.loads(val)
        except Exception:
            parsed = val
        return {
            "category": r["category"],
            "key": r["key"],
            "value": parsed,
            "confidence": r["confidence"],
            "updated_at": r["updated_at"],
        }

    # ── Conversation History Operations ────────────────────────────────────────

    def add_conversation_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        now = time.time()
        meta_str = json.dumps(metadata or {})
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO conversation_turns (session_id, role, content, metadata_json, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, role, content, meta_str, now))
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()

    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, session_id, role, content, metadata_json, timestamp
                    FROM conversation_turns
                    WHERE session_id = ?
                    ORDER BY timestamp ASC
                    LIMIT ?
                """, (session_id, limit))
                rows = cursor.fetchall()
                return [
                    {
                        "id": r["id"],
                        "session_id": r["session_id"],
                        "role": r["role"],
                        "content": r["content"],
                        "metadata": json.loads(r["metadata_json"]),
                        "timestamp": r["timestamp"],
                    }
                    for r in rows
                ]
            finally:
                conn.close()

    # ── Recipe Operations ──────────────────────────────────────────────────────

    def save_recipe(
        self,
        name: str,
        goal_pattern: str,
        steps: List[Dict[str, Any]],
    ) -> None:
        now = time.time()
        steps_json = json.dumps(steps)
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO recipes (name, goal_pattern, steps_json, created_at, usage_count, last_used_at)
                    VALUES (?, ?, ?, ?, 0, 0.0)
                    ON CONFLICT(name) DO UPDATE SET
                        goal_pattern = excluded.goal_pattern,
                        steps_json = excluded.steps_json
                """, (name, goal_pattern, steps_json, now))
                conn.commit()
                logger.debug(f"Saved recipe '{name}'")
            finally:
                conn.close()

    def get_recipe(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name, goal_pattern, steps_json, usage_count, last_used_at FROM recipes WHERE name = ?",
                    (name,),
                )
                r = cursor.fetchone()
                if not r:
                    return None
                return {
                    "name": r["name"],
                    "goal_pattern": r["goal_pattern"],
                    "steps": json.loads(r["steps_json"]),
                    "usage_count": r["usage_count"],
                    "last_used_at": r["last_used_at"],
                }
            finally:
                conn.close()

    def list_recipes(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT name, goal_pattern, steps_json, usage_count, last_used_at FROM recipes ORDER BY usage_count DESC")
                rows = cursor.fetchall()
                return [
                    {
                        "name": r["name"],
                        "goal_pattern": r["goal_pattern"],
                        "steps": json.loads(r["steps_json"]),
                        "usage_count": r["usage_count"],
                        "last_used_at": r["last_used_at"],
                    }
                    for r in rows
                ]
            finally:
                conn.close()

    def increment_recipe_usage(self, name: str) -> None:
        now = time.time()
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE recipes
                    SET usage_count = usage_count + 1, last_used_at = ?
                    WHERE name = ?
                """, (now, name))
                conn.commit()
            finally:
                conn.close()
