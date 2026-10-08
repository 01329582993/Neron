"""Comprehensive test suite for Neron Stage 8 Computer Vision and Screen Reasoning subsystem."""

import os
from pathlib import Path
import tempfile
import numpy as np
from PIL import Image, ImageDraw
import pytest

from neron.computer.base import CursorPosition, KeyboardController, MouseController
from neron.core.planner.dag_planner import DAGPlanner
from neron.core.state.models import TaskState
from neron.security.permissions import Capability
from neron.tools import create_default_registry
from neron.tools.vision.tools import (
    VisionClickElementTool,
    VisionFindElementTool,
    VisionScreenshotTool,
    VisionTypeTextTool,
)
from neron.vision.analyzer import (
    BoundingBox,
    DetectedElement,
    ScreenAnalyzer,
)
from neron.vision.capture import ScreenCapture, ScreenshotResult
from neron.vision.coordinator import VisionCoordinator
from neron.vision.locator import ElementLocator, ElementNotFoundError


# ── Mock Controllers for Headless Testing ───────────────────────────────────

class MockMouse(MouseController):
    def __init__(self):
        self.pos = CursorPosition(0, 0)
        self.clicks = []

    def get_position(self) -> CursorPosition:
        return self.pos

    def move_to(self, x: int, y: int) -> bool:
        self.pos = CursorPosition(x, y)
        return True

    def click(self, button: str = "left", count: int = 1) -> bool:
        self.clicks.append((self.pos.x, self.pos.y, button, count))
        return True

    def scroll(self, clicks: int) -> bool:
        return True


class MockKeyboard(KeyboardController):
    def __init__(self):
        self.typed = []
        self.keys = []
        self.hotkeys = []

    def type_text(self, text: str) -> bool:
        self.typed.append(text)
        return True

    def press_key(self, key_name: str) -> bool:
        self.keys.append(key_name)
        return True

    def hotkey(self, *keys: str) -> bool:
        self.hotkeys.append(keys)
        return True


# ── Helper for Synthetic Test Images ────────────────────────────────────────

def create_synthetic_screen(width: int = 400, height: int = 300) -> Image.Image:
    """Create a test image with background and distinct shapes/buttons."""
    img = Image.new("RGB", (width, height), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)

    # Draw a simulated button at (50, 50) of size 100x40 (aspect ratio 2.5)
    draw.rectangle([50, 50, 150, 90], fill=(0, 120, 215), outline=(0, 90, 180), width=2)

    # Draw a button in the bottom right: (260, 220) size 100x40
    draw.rectangle([260, 220, 360, 260], fill=(220, 50, 50), outline=(180, 30, 30), width=2)

    return img


# ── Test Screen Capture ──────────────────────────────────────────────────────

class TestScreenCapture:
    def test_mock_screen_capture(self):
        capture = ScreenCapture()
        mock_img = create_synthetic_screen(400, 300)
        capture.set_mock_image(mock_img)

        result = capture.capture(monitor=1)
        assert isinstance(result, ScreenshotResult)
        assert result.width == 400
        assert result.height == 300
        assert len(result.image_bytes) > 0
        assert result.monitor == 1

    def test_screen_capture_with_region(self):
        capture = ScreenCapture()
        mock_img = create_synthetic_screen(400, 300)
        capture.set_mock_image(mock_img)

        region = (50, 50, 100, 40)
        result = capture.capture(region=region)
        assert result.width == 100
        assert result.height == 40

    def test_screen_capture_save_to_file(self):
        capture = ScreenCapture()
        mock_img = create_synthetic_screen(200, 200)
        capture.set_mock_image(mock_img)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            temp_path = tf.name

        try:
            result = capture.capture(output_path=temp_path)
            assert os.path.exists(temp_path)
            assert os.path.getsize(temp_path) > 0
            assert result.file_path == temp_path
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


# ── Test Screen Analyzer ────────────────────────────────────────────────────

class TestScreenAnalyzer:
    def test_template_matching_exact(self):
        screen = create_synthetic_screen(400, 300)
        # Template is the exact button at (50, 50) of size (100, 40)
        template = screen.crop((50, 50, 150, 90))

        analyzer = ScreenAnalyzer()
        matches = analyzer.match_template(screen, template, threshold=0.9)

        assert len(matches) >= 1
        best = matches[0]
        assert best.confidence >= 0.95
        assert abs(best.bbox.x - 50) <= 2
        assert abs(best.bbox.y - 50) <= 2
        assert best.bbox.width == 100
        assert best.bbox.height == 40
        assert best.center == (best.bbox.x + 50, best.bbox.y + 20)

    def test_ui_element_contour_detection(self):
        screen = create_synthetic_screen(400, 300)
        analyzer = ScreenAnalyzer()
        elements = analyzer.detect_ui_elements(screen, min_width=30, min_height=20)

        assert len(elements) >= 2
        types = [e.element_type for e in elements]
        assert "button" in types

    def test_crop_element(self):
        screen = create_synthetic_screen(400, 300)
        analyzer = ScreenAnalyzer()
        bbox = BoundingBox(x=50, y=50, width=100, height=40)
        cropped = analyzer.crop_element(screen, bbox)

        assert cropped.width == 100
        assert cropped.height == 40


# ── Test Element Locator ────────────────────────────────────────────────────

class TestElementLocator:
    def test_locate_by_spatial_region(self):
        locator = ElementLocator()
        box = locator.get_spatial_region_box(600, 600, "bottom_right")
        assert box.x == 400
        assert box.y == 400
        assert box.width == 200
        assert box.height == 200

    def test_locate_element_in_bottom_right(self):
        screen = create_synthetic_screen(400, 300)
        locator = ElementLocator()

        # Target the button we drew in the bottom right (260, 220)
        elem = locator.locate_by_description(screen, "button in bottom right")
        assert elem is not None
        # Center should be in bottom right quadrant (x > 200, y > 150)
        assert elem.center[0] > 200
        assert elem.center[1] > 150

    def test_locate_template_not_found_raises_error(self):
        screen = create_synthetic_screen(400, 300)
        # Unique shape that does not exist in screen
        fake_template = Image.new("RGB", (50, 50), color=(12, 34, 56))

        locator = ElementLocator()
        with pytest.raises(ElementNotFoundError):
            locator.locate_template(screen, fake_template, threshold=0.95)


# ── Test Vision Coordinator ─────────────────────────────────────────────────

class TestVisionCoordinator:
    def test_coordinator_click_with_mock(self):
        capture = ScreenCapture()
        capture.set_mock_image(create_synthetic_screen(400, 300))
        mock_mouse = MockMouse()
        mock_kb = MockKeyboard()

        coord = VisionCoordinator(
            capture=capture,
            mouse=mock_mouse,
            keyboard=mock_kb,
        )

        res = coord.click(x=120, y=80, button="left", clicks=1)
        assert res["clicked"] is True
        assert res["x"] == 120
        assert res["y"] == 80
        assert mock_mouse.pos.x == 120
        assert mock_mouse.pos.y == 80
        assert len(mock_mouse.clicks) == 1

    def test_coordinator_type_text(self):
        mock_kb = MockKeyboard()
        coord = VisionCoordinator(keyboard=mock_kb)

        ok = coord.type_text("Neron Agent", press_enter=True)
        assert ok is True
        assert "Neron Agent" in mock_kb.typed
        assert "enter" in mock_kb.keys


# ── Test Vision Tools in Tool Registry ──────────────────────────────────────

class TestVisionTools:
    def test_vision_tools_registered_in_default_registry(self):
        registry = create_default_registry()
        assert registry.has("vision.screenshot")
        assert registry.has("vision.find_element")
        assert registry.has("vision.click_element")
        assert registry.has("vision.type_text")

    def test_screenshot_tool_execution(self):
        capture = ScreenCapture()
        capture.set_mock_image(create_synthetic_screen(300, 200))
        coord = VisionCoordinator(capture=capture)
        tool = VisionScreenshotTool(coordinator=coord)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            out_path = tf.name

        try:
            res = tool.execute({"output_path": out_path})
            assert res.success is True
            assert res.output["width"] == 300
            assert res.output["height"] == 200
            assert os.path.exists(out_path)
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)

    def test_click_element_tool_capabilities(self):
        tool = VisionClickElementTool()
        assert Capability.COMPUTER_MOUSE in tool.required_capabilities

    def test_type_text_tool_execution(self):
        mock_kb = MockKeyboard()
        coord = VisionCoordinator(keyboard=mock_kb)
        tool = VisionTypeTextTool(coordinator=coord)

        res = tool.execute({"text": "Hello World", "press_enter": True})
        assert res.success is True
        assert "Hello World" in mock_kb.typed
        assert "enter" in mock_kb.keys



# ── Test DAG Planner with Vision Goals ──────────────────────────────────────

class TestVisionDAGPlanner:
    def test_screenshot_goal_planning(self):
        planner = DAGPlanner()
        plan = planner.plan("take a screenshot", {}, [])

        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "vision.screenshot"
        assert plan.state == TaskState.PENDING

    def test_click_button_multi_step_dag(self):
        planner = DAGPlanner()
        plan = planner.plan("click the submit button", {}, [])

        assert len(plan.steps) == 2
        find_step = plan.steps[0]
        click_step = plan.steps[1]

        assert find_step.tool_name == "vision.find_element"
        assert click_step.tool_name == "vision.click_element"
        assert click_step.depends_on == [find_step.step_id]

    def test_click_then_type_dag(self):
        planner = DAGPlanner()
        plan = planner.plan("click search box then type 'pytest'", {}, [])

        assert len(plan.steps) == 2
        click_step = plan.steps[0]
        type_step = plan.steps[1]

        assert click_step.tool_name == "vision.click_element"
        assert type_step.tool_name == "vision.type_text"
        assert type_step.arguments["text"] == "pytest"
        assert type_step.depends_on == [click_step.step_id]

    def test_find_on_screen_goal(self):
        planner = DAGPlanner()
        plan = planner.plan("find login button on screen", {}, [])

        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "vision.find_element"
        assert "login button" in plan.steps[0].arguments["description"]
