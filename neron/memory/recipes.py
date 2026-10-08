"""Procedural automation recipe manager for reusable task workflows."""

import re
from typing import Any, Dict, List, Optional

from neron.memory.sqlite_store import SQLiteMemoryStore
from neron.utils.logger import get_logger

logger = get_logger("memory.recipes")


class RecipeManager:
    """
    Manages procedural automation workflows (recipes) and matches incoming goals to known recipes.
    """

    def __init__(self, store: SQLiteMemoryStore):
        self.store = store

    def register_recipe(
        self,
        name: str,
        goal_pattern: str,
        steps: List[Dict[str, Any]],
    ) -> None:
        """Register or update an automation recipe."""
        self.store.save_recipe(name=name, goal_pattern=goal_pattern, steps=steps)
        logger.info(f"Registered recipe: '{name}' (Pattern: {goal_pattern})")

    def get_recipe(self, name: str) -> Optional[Dict[str, Any]]:
        return self.store.get_recipe(name)

    def list_recipes(self) -> List[Dict[str, Any]]:
        return self.store.list_recipes()

    def find_matching_recipe(self, goal: str) -> Optional[Dict[str, Any]]:
        """
        Check if goal matches any registered recipe pattern.
        Returns recipe dictionary and increments usage count if found.
        """
        recipes = self.store.list_recipes()
        clean = goal.strip()

        for rec in recipes:
            pat = rec["goal_pattern"]
            try:
                if re.search(pat, clean, re.IGNORECASE):
                    self.store.increment_recipe_usage(rec["name"])
                    rec["usage_count"] += 1
                    return rec
            except Exception as e:
                logger.warning(f"Invalid regex in recipe '{rec['name']}': {e}")
                if pat.lower() in clean.lower():
                    self.store.increment_recipe_usage(rec["name"])
                    rec["usage_count"] += 1
                    return rec


        return None
