"""Test suite for Neron Stage 9 Memory Subsystem."""

import os
from pathlib import Path
import tempfile
import pytest

from neron.core.planner.dag_planner import DAGPlanner
from neron.core.state.models import TaskState
from neron.memory.manager import MemoryManager
from neron.memory.recipes import RecipeManager
from neron.memory.sqlite_store import SQLiteMemoryStore
from neron.memory.working_memory import WorkingMemory
from neron.security.permissions import Capability
from neron.tools import create_default_registry
from neron.tools.memory.tools import (
    MemoryForgetTool,
    MemoryRecallTool,
    MemoryRememberTool,
)


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name
    yield db_path
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass



# ── SQLite Store Tests ──────────────────────────────────────────────────────

class TestSQLiteMemoryStore:
    def test_store_and_get_fact(self, temp_db):
        store = SQLiteMemoryStore(db_path=temp_db)
        store.store_fact(key="editor", value="VSCode", category="preferences")

        val = store.get_fact(key="editor", category="preferences")
        assert val == "VSCode"

    def test_update_existing_fact(self, temp_db):
        store = SQLiteMemoryStore(db_path=temp_db)
        store.store_fact(key="theme", value="dark", category="ui")
        store.store_fact(key="theme", value="light", category="ui")

        val = store.get_fact(key="theme", category="ui")
        assert val == "light"

    def test_delete_fact(self, temp_db):
        store = SQLiteMemoryStore(db_path=temp_db)
        store.store_fact(key="temp_key", value="temp_val")
        assert store.get_fact("temp_key") == "temp_val"

        deleted = store.delete_fact("temp_key")
        assert deleted is True
        assert store.get_fact("temp_key") is None

    def test_list_and_search_facts(self, temp_db):
        store = SQLiteMemoryStore(db_path=temp_db)
        store.store_fact(key="browser", value="Firefox", category="apps")
        store.store_fact(key="player", value="VLC", category="apps")
        store.store_fact(key="font_size", value="14", category="ui")

        apps = store.list_facts(category="apps")
        assert len(apps) == 2

        search_results = store.search_facts("Firefox")
        assert len(search_results) >= 1
        assert search_results[0]["key"] == "browser"

    def test_conversation_turns(self, temp_db):
        store = SQLiteMemoryStore(db_path=temp_db)
        store.add_conversation_turn("sess_1", "user", "Hello Neron")
        store.add_conversation_turn("sess_1", "assistant", "Hello! How can I help?")

        history = store.get_conversation_history("sess_1")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["content"] == "Hello! How can I help?"

    def test_recipe_lifecycle(self, temp_db):
        store = SQLiteMemoryStore(db_path=temp_db)
        steps = [{"tool_name": "system.telemetry", "arguments": {}}]
        store.save_recipe(name="check_system", goal_pattern=r"check\s+health", steps=steps)

        recipe = store.get_recipe("check_system")
        assert recipe is not None
        assert recipe["goal_pattern"] == r"check\s+health"
        assert len(recipe["steps"]) == 1

        store.increment_recipe_usage("check_system")
        updated = store.get_recipe("check_system")
        assert updated["usage_count"] == 1


# ── Working Memory Tests ────────────────────────────────────────────────────

class TestWorkingMemory:
    def test_variables(self):
        wm = WorkingMemory()
        wm.set_variable("last_file", "C:/test.txt")
        assert wm.get_variable("last_file") == "C:/test.txt"

        deleted = wm.delete_variable("last_file")
        assert deleted is True
        assert wm.get_variable("last_file") is None

    def test_goal_and_turn_history(self):
        wm = WorkingMemory(max_history=3)
        wm.set_goal("clean workspace", plan_id="p-123")
        assert wm.current_goal == "clean workspace"
        assert wm.active_plan_id == "p-123"

        wm.add_turn("user", "turn 1")
        wm.add_turn("assistant", "turn 2")
        wm.add_turn("user", "turn 3")
        wm.add_turn("assistant", "turn 4")

        # Sliding window keeps max 3
        history = wm.get_recent_history()
        assert len(history) == 3
        assert history[0]["content"] == "turn 2"
        assert history[2]["content"] == "turn 4"

    def test_clear_working_memory(self):
        wm = WorkingMemory()
        wm.set_variable("foo", "bar")
        wm.set_goal("some goal")
        wm.clear()

        assert wm.current_goal is None
        assert wm.get_variable("foo") is None
        assert len(wm.history) == 0


# ── Recipe Manager Tests ────────────────────────────────────────────────────

class TestRecipeManager:
    def test_recipe_registration_and_matching(self, temp_db):
        store = SQLiteMemoryStore(db_path=temp_db)
        rm = RecipeManager(store=store)

        rm.register_recipe(
            name="morning_routine",
            goal_pattern=r"start\s+my\s+day",
            steps=[
                {"tool_name": "system.volume", "arguments": {"level": 50}},
                {"tool_name": "system.open_app", "arguments": {"app_name": "chrome"}},
            ],
        )

        matched = rm.find_matching_recipe("hey neron, start my day please")
        assert matched is not None
        assert matched["name"] == "morning_routine"
        assert len(matched["steps"]) == 2
        assert matched["usage_count"] == 1

        assert rm.find_matching_recipe("completely unrelated task") is None


# ── Memory Manager Tests ────────────────────────────────────────────────────

class TestMemoryManager:
    def test_remember_recall_and_context(self, temp_db):
        mm = MemoryManager(db_path=temp_db)
        mm.remember(key="username", value="Lima", category="profile")
        mm.remember(key="shell", value="powershell", category="env")

        assert mm.recall("username") == "Lima"
        assert mm.recall("shell") == "powershell"

        mm.record_interaction("user", "What is my shell?")
        mm.record_interaction("assistant", "Your shell is powershell.")

        context = mm.get_prompt_context()
        assert "Known User Facts & Preferences:" in context
        assert "username: Lima" in context
        assert "Recent Context:" in context
        assert "What is my shell?" in context


# ── Memory Tools Tests ──────────────────────────────────────────────────────

class TestMemoryTools:
    def test_memory_tools_registered_in_default_registry(self):
        reg = create_default_registry()
        assert reg.has("memory.remember")
        assert reg.has("memory.recall")
        assert reg.has("memory.forget")

    def test_remember_and_recall_tool_execution(self, temp_db):
        mm = MemoryManager(db_path=temp_db)
        rem_tool = MemoryRememberTool(memory_manager=mm)
        rec_tool = MemoryRecallTool(memory_manager=mm)
        for_tool = MemoryForgetTool(memory_manager=mm)

        # Store
        res1 = rem_tool.execute({"key": "favorite_food", "value": "Pizza"})
        assert res1.success is True
        assert res1.output["saved"] is True

        # Recall
        res2 = rec_tool.execute({"key": "favorite_food"})
        assert res2.success is True
        assert res2.output["value"] == "Pizza"
        assert res2.output["found"] is True

        # Forget
        res3 = for_tool.execute({"key": "favorite_food"})
        assert res3.success is True
        assert res3.output["deleted"] is True

        # Recall again
        res4 = rec_tool.execute({"key": "favorite_food"})
        assert res4.output["found"] is False


# ── DAG Planner Memory Goals Tests ──────────────────────────────────────────

class TestDAGPlannerMemoryGoals:
    def test_remember_goal(self):
        planner = DAGPlanner()
        plan = planner.plan("remember that default_browser is brave", {}, [])

        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "memory.remember"
        assert plan.steps[0].arguments["key"] == "default_browser"
        assert plan.steps[0].arguments["value"] == "brave"

    def test_recall_goal(self):
        planner = DAGPlanner()
        plan = planner.plan("recall default_browser", {}, [])

        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "memory.recall"
        assert plan.steps[0].arguments["key"] == "default_browser"

    def test_forget_goal(self):
        planner = DAGPlanner()
        plan = planner.plan("forget default_browser", {}, [])

        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "memory.forget"
        assert plan.steps[0].arguments["key"] == "default_browser"

    def test_recipe_in_context_expands_into_plan(self, temp_db):
        store = SQLiteMemoryStore(db_path=temp_db)
        rm = RecipeManager(store=store)
        rm.register_recipe(
            name="podcast_prep",
            goal_pattern=r"record\s+podcast",
            steps=[
                {"tool_name": "system.volume", "arguments": {"level": 80}},
                {"tool_name": "system.open_app", "arguments": {"app_name": "audacity"}},
            ],
        )

        planner = DAGPlanner()
        plan = planner.plan("record podcast now", {"recipe_manager": rm}, [])

        assert len(plan.steps) == 2
        assert plan.steps[0].tool_name == "system.volume"
        assert plan.steps[1].tool_name == "system.open_app"
