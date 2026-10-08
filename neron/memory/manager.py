"""Unified Memory Subsystem facade coordinating persistent facts, working state, and recipes."""

from typing import Any, Dict, List, Optional

from neron.memory.recipes import RecipeManager
from neron.memory.sqlite_store import SQLiteMemoryStore
from neron.memory.working_memory import WorkingMemory
from neron.utils.logger import get_logger

logger = get_logger("memory.manager")


class MemoryManager:
    """
    Main entry point for memory in Neron:
    - Persistent facts (user preferences, system paths, learned knowledge)
    - Working memory (active session scratchpad, variables)
    - Procedural recipes (multi-step workflow templates)
    """

    def __init__(self, db_path: Optional[str] = None):
        self.store = SQLiteMemoryStore(db_path=db_path)
        self.working_memory = WorkingMemory()
        self.recipes = RecipeManager(store=self.store)

    # ── Fact API ───────────────────────────────────────────────────────────────

    def remember(
        self,
        key: str,
        value: Any,
        category: str = "general",
        confidence: float = 1.0,
    ) -> None:
        """Store or update a persistent fact."""
        self.store.store_fact(key=key, value=value, category=category, confidence=confidence)

    def recall(self, key: str, category: Optional[str] = None) -> Optional[Any]:
        """Retrieve a specific fact by key."""
        return self.store.get_fact(key=key, category=category)

    def search(self, query: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search memory facts using full-text or substring query."""
        return self.store.search_facts(query=query, category=category)

    def forget(self, key: str, category: Optional[str] = None) -> bool:
        """Delete a fact from persistent memory."""
        return self.store.delete_fact(key=key, category=category)

    def list_facts(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List stored facts."""
        return self.store.list_facts(category=category)

    # ── Conversational Turn Recording ──────────────────────────────────────────

    def record_interaction(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record turn into both volatile working memory and persistent SQLite history."""
        self.working_memory.add_turn(role=role, content=content, metadata=metadata)
        self.store.add_conversation_turn(
            session_id=self.working_memory.session_id,
            role=role,
            content=content,
            metadata=metadata,
        )

    # ── Context Summarization for LLM ──────────────────────────────────────────

    def get_prompt_context(self, max_facts: int = 5) -> str:
        """
        Assemble relevant memory facts and recent turns for LLM prompt context injection.
        """
        sections: List[str] = []

        # 1. Key persistent facts
        facts = self.store.list_facts()
        if facts:
            fact_lines = [f"- [{f['category']}] {f['key']}: {f['value']}" for f in facts[:max_facts]]
            sections.append("Known User Facts & Preferences:\n" + "\n".join(fact_lines))

        # 2. Recent conversational turns
        recent_turns = self.working_memory.get_recent_history(count=4)
        if recent_turns:
            turn_lines = [f"{t['role'].capitalize()}: {t['content']}" for t in recent_turns]
            sections.append("Recent Context:\n" + "\n".join(turn_lines))

        return "\n\n".join(sections)
