"""Implementation of neron-media-controller plugin."""

import os
from typing import Any, Dict, List

from neron.computer.native_windows import NativeWindowsKeyboard
from neron.plugins.base import PluginBase
from neron.security.permissions import Capability
from neron.tools.base import BaseTool, ToolResult
from neron.tools.registry import ToolRegistry


class MediaPlayPauseTool(BaseTool):
    """Tool to toggle media play/pause."""

    def __init__(self):
        self.keyboard = NativeWindowsKeyboard() if os.name == "nt" else None

    @property
    def name(self) -> str:
        return "media.play_pause"

    @property
    def description(self) -> str:
        return "Toggle play/pause state for current media playback."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.COMPUTER_KEYBOARD]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        try:
            # VK_MEDIA_PLAY_PAUSE is 0xB3 on Windows
            if os.name == "nt" and self.keyboard:
                import ctypes
                user32 = ctypes.windll.user32
                user32.keybd_event(0xB3, 0, 0, 0)
                user32.keybd_event(0xB3, 0, 2, 0) # keyup
            return ToolResult(success=True, output={"action": "toggle_play_pause"})
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Media action failed: {e}")


class MediaNextTool(BaseTool):
    """Tool to skip to next media track."""

    def __init__(self):
        self.keyboard = NativeWindowsKeyboard() if os.name == "nt" else None

    @property
    def name(self) -> str:
        return "media.next"

    @property
    def description(self) -> str:
        return "Skip to next track in active media player."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}

    @property
    def required_capabilities(self) -> List[str]:
        return [Capability.COMPUTER_KEYBOARD]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        try:
            # VK_MEDIA_NEXT_TRACK is 0xB0 on Windows
            if os.name == "nt" and self.keyboard:
                import ctypes
                user32 = ctypes.windll.user32
                user32.keybd_event(0xB0, 0, 0, 0)
                user32.keybd_event(0xB0, 0, 2, 0)
            return ToolResult(success=True, output={"action": "next_track"})
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Next track action failed: {e}")


class MediaControllerPlugin(PluginBase):
    """Lifecycle controller for MediaController plugin."""

    def __init__(self, metadata=None, config=None):
        super().__init__(metadata=metadata, config=config)
        self.play_tool = MediaPlayPauseTool()
        self.next_tool = MediaNextTool()

    def on_load(self) -> bool:
        self.logger.debug("MediaControllerPlugin loaded.")
        return True

    def on_enable(self, registry: ToolRegistry) -> None:
        registry.register(self.play_tool)
        registry.register(self.next_tool)
        self.logger.info("MediaControllerPlugin tools registered.")

    def on_disable(self, registry: ToolRegistry) -> None:
        registry.unregister("media.play_pause")
        registry.unregister("media.next")
        self.logger.info("MediaControllerPlugin tools unregistered.")
