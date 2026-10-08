"""High-level coordinator orchestrating screen capture, vision analysis, and GUI interactions."""

import os
import time
from typing import Any, Dict, List, Optional, Tuple

from neron.computer.base import MouseController, KeyboardController
from neron.computer.native_windows import NativeWindowsMouse, NativeWindowsKeyboard
from neron.utils.logger import get_logger
from neron.vision.analyzer import DetectedElement, ScreenAnalyzer
from neron.vision.capture import ScreenCapture, ScreenshotResult
from neron.vision.locator import ElementLocator, ElementNotFoundError

logger = get_logger("vision.coordinator")


class VisionCoordinator:
    """
    Coordinates visual capture, element reasoning, and desktop mouse/keyboard automation.
    """

    def __init__(
        self,
        capture: Optional[ScreenCapture] = None,
        analyzer: Optional[ScreenAnalyzer] = None,
        locator: Optional[ElementLocator] = None,
        mouse: Optional[MouseController] = None,
        keyboard: Optional[KeyboardController] = None,
    ):
        self.capture = capture or ScreenCapture()
        self.analyzer = analyzer or ScreenAnalyzer()
        self.locator = locator or ElementLocator(analyzer=self.analyzer)
        self.mouse = mouse or self._get_default_mouse()
        self.keyboard = keyboard or self._get_default_keyboard()

    def _get_default_mouse(self) -> MouseController:
        if os.name == "nt":
            return NativeWindowsMouse()
        # Fallback or stub for non-Windows
        return NativeWindowsMouse()

    def _get_default_keyboard(self) -> KeyboardController:
        if os.name == "nt":
            return NativeWindowsKeyboard()
        return NativeWindowsKeyboard()

    def take_screenshot(
        self,
        output_path: Optional[str] = None,
        monitor: int = 1,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> ScreenshotResult:
        """Capture screenshot and optionally save to file."""
        return self.capture.capture(monitor=monitor, region=region, output_path=output_path)

    def find_element(
        self,
        template_path: Optional[str] = None,
        description: Optional[str] = None,
        threshold: float = 0.8,
        monitor: int = 1,
    ) -> DetectedElement:
        """
        Capture the screen and locate an element by template or visual description.
        """
        screenshot = self.take_screenshot(monitor=monitor)
        desc = description or "visual element"
        return self.locator.locate_by_description(
            image_input=screenshot.image,
            description=desc,
            template_input=template_path,
            threshold=threshold,
        )

    def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        template_path: Optional[str] = None,
        description: Optional[str] = None,
        button: str = "left",
        clicks: int = 1,
        monitor: int = 1,
    ) -> Dict[str, Any]:
        """
        Click at explicit (x, y) coordinates or visually locate target before clicking.
        """
        target_x = x
        target_y = y
        target_element = None

        if target_x is None or target_y is None:
            if not template_path and not description:
                raise ValueError("Must provide either (x, y) or a template_path / description.")
            target_element = self.find_element(
                template_path=template_path,
                description=description,
                monitor=monitor,
            )
            target_x, target_y = target_element.center

        # Move mouse and click
        self.mouse.move_to(target_x, target_y)
        time.sleep(0.05)
        success = self.mouse.click(button=button, count=clicks)

        logger.info(f"Clicked at ({target_x}, {target_y}) with {button} button (clicks={clicks})")
        return {
            "clicked": success,
            "x": target_x,
            "y": target_y,
            "button": button,
            "clicks": clicks,
            "element": target_element.to_dict() if target_element else None,
        }

    def type_text(self, text: str, press_enter: bool = False) -> bool:
        """Synthesize typing into currently focused UI element."""
        success = self.keyboard.type_text(text)
        if press_enter:
            time.sleep(0.05)
            self.keyboard.press_key("enter")
        return success

    def hotkey(self, *keys: str) -> bool:
        """Trigger a keyboard shortcut combination."""
        return self.keyboard.hotkey(*keys)
