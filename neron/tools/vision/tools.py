"""Tools exposing computer vision and GUI control capabilities to Neron."""

import os
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, List, Optional

from neron.security.permissions import Capability
from neron.tools.base import BaseTool, ToolResult
from neron.vision.coordinator import VisionCoordinator
from neron.vision.locator import ElementNotFoundError


class VisionScreenshotTool(BaseTool):
    """Captures a screenshot of the desktop or a specific region."""

    def __init__(self, coordinator: Optional[VisionCoordinator] = None):
        self.coordinator = coordinator or VisionCoordinator()

    @property
    def name(self) -> str:
        return "vision.screenshot"

    @property
    def description(self) -> str:
        return "Capture desktop screenshot, save to file, and return metadata."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "output_path": {"type": "string", "description": "Optional file path to save screenshot PNG."},
                "monitor": {"type": "integer", "description": "Monitor index to capture (default: 1).", "default": 1},
                "region": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Optional bounding box [x, y, width, height] to crop.",
                },
            },
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.COMPUTER_SCREEN]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        output_path = arguments.get("output_path")
        monitor = arguments.get("monitor", 1)
        region = arguments.get("region")

        try:
            target_path = output_path
            if not target_path:
                temp_dir = Path(tempfile.gettempdir()) / "neron_screenshots"
                temp_dir.mkdir(parents=True, exist_ok=True)
                target_path = str(temp_dir / f"screenshot_{int(time.time() * 1000)}.png")

            reg_tuple = tuple(region) if region and len(region) == 4 else None
            result = self.coordinator.take_screenshot(
                output_path=target_path,
                monitor=monitor,
                region=reg_tuple,
            )

            return ToolResult(
                success=True,
                output={
                    "path": result.file_path or target_path,
                    "width": result.width,
                    "height": result.height,
                    "monitor": result.monitor,
                    "timestamp": result.timestamp,
                },
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Screenshot capture failed: {e}")


class VisionFindElementTool(BaseTool):
    """Finds a visual element or template match on the active screen."""

    def __init__(self, coordinator: Optional[VisionCoordinator] = None):
        self.coordinator = coordinator or VisionCoordinator()

    @property
    def name(self) -> str:
        return "vision.find_element"

    @property
    def description(self) -> str:
        return "Locate a visual element, button, or template on screen by description or template path."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "template_path": {"type": "string", "description": "Path to template image file to find."},
                "description": {"type": "string", "description": "Visual or spatial description (e.g. 'button in bottom right')."},
                "threshold": {"type": "number", "description": "Match confidence threshold (0.0 to 1.0, default 0.8).", "default": 0.8},
                "monitor": {"type": "integer", "description": "Monitor index to inspect.", "default": 1},
            },
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.COMPUTER_SCREEN]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        template_path = arguments.get("template_path")
        description = arguments.get("description")
        threshold = float(arguments.get("threshold", 0.8))
        monitor = int(arguments.get("monitor", 1))

        try:
            element = self.coordinator.find_element(
                template_path=template_path,
                description=description,
                threshold=threshold,
                monitor=monitor,
            )
            return ToolResult(
                success=True,
                output=element.to_dict(),
            )
        except ElementNotFoundError as e:
            return ToolResult(success=False, output=None, error=f"Element not found: {e}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Vision find error: {e}")


class VisionClickElementTool(BaseTool):
    """Clicks on screen coordinates or locates an element visually to click it."""

    def __init__(self, coordinator: Optional[VisionCoordinator] = None):
        self.coordinator = coordinator or VisionCoordinator()

    @property
    def name(self) -> str:
        return "vision.click_element"

    @property
    def description(self) -> str:
        return "Click on screen coordinates (x, y) or visually locate an element by description/template."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "Target X screen coordinate."},
                "y": {"type": "integer", "description": "Target Y screen coordinate."},
                "template_path": {"type": "string", "description": "Path to template image to locate and click."},
                "description": {"type": "string", "description": "Visual description of target element."},
                "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
                "clicks": {"type": "integer", "default": 1},
                "monitor": {"type": "integer", "default": 1},
            },
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.COMPUTER_MOUSE]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        x = arguments.get("x")
        y = arguments.get("y")
        template_path = arguments.get("template_path")
        description = arguments.get("description")
        button = arguments.get("button", "left")
        clicks = int(arguments.get("clicks", 1))
        monitor = int(arguments.get("monitor", 1))

        try:
            res = self.coordinator.click(
                x=x,
                y=y,
                template_path=template_path,
                description=description,
                button=button,
                clicks=clicks,
                monitor=monitor,
            )
            return ToolResult(success=True, output=res)
        except ElementNotFoundError as e:
            return ToolResult(success=False, output=None, error=f"Click target not found: {e}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Click execution failed: {e}")


class VisionTypeTextTool(BaseTool):
    """Simulates keyboard input into the focused desktop window."""

    def __init__(self, coordinator: Optional[VisionCoordinator] = None):
        self.coordinator = coordinator or VisionCoordinator()

    @property
    def name(self) -> str:
        return "vision.type_text"

    @property
    def description(self) -> str:
        return "Type text string into currently focused application window."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {"type": "string", "description": "Text to type into active window."},
                "press_enter": {"type": "boolean", "description": "Whether to press enter key after typing.", "default": False},
            },
        }

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.COMPUTER_KEYBOARD]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        text = arguments.get("text", "")
        press_enter = bool(arguments.get("press_enter", False))

        try:
            ok = self.coordinator.type_text(text=text, press_enter=press_enter)
            return ToolResult(
                success=ok,
                output={"typed": text, "enter_pressed": press_enter},
                error=None if ok else "Failed to send keystrokes",
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Type text error: {e}")
