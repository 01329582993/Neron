"""Native Windows desktop input and screen capture using ctypes and Pillow."""

import ctypes
import os
from pathlib import Path
import time
from typing import Dict, Optional, Tuple

from neron.computer.base import (
    CursorPosition,
    KeyboardController,
    MouseController,
    ScreenCapture,
    ScreenResolution,
)
from neron.utils.logger import get_logger

logger = get_logger("computer.native_windows")

user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None

# Mouse Flags
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800

# Keyboard Flags
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

# Common Virtual Key Codes
VK_MAP: Dict[str, int] = {
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "space": 0x20,
    "backspace": 0x08,
    "escape": 0x1B,
    "esc": 0x1B,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "win": 0x5B,
    "windows": 0x5B,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "delete": 0x2E,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
}


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class NativeWindowsMouse(MouseController):
    """Zero-dependency mouse control via Windows User32."""

    def get_position(self) -> CursorPosition:
        if not user32:
            return CursorPosition(x=0, y=0)
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return CursorPosition(x=pt.x, y=pt.y)

    def move_to(self, x: int, y: int) -> bool:
        if not user32:
            return False
        user32.SetCursorPos(int(x), int(y))
        return True

    def click(self, button: str = "left", count: int = 1) -> bool:
        if not user32:
            return False
        btn = button.lower()
        down_flag = MOUSEEVENTF_LEFTDOWN
        up_flag = MOUSEEVENTF_LEFTUP

        if btn == "right":
            down_flag = MOUSEEVENTF_RIGHTDOWN
            up_flag = MOUSEEVENTF_RIGHTUP
        elif btn == "middle":
            down_flag = MOUSEEVENTF_MIDDLEDOWN
            up_flag = MOUSEEVENTF_MIDDLEUP

        for _ in range(count):
            user32.mouse_event(down_flag, 0, 0, 0, 0)
            time.sleep(0.05)
            user32.mouse_event(up_flag, 0, 0, 0, 0)
            if count > 1:
                time.sleep(0.1)
        return True

    def scroll(self, clicks: int) -> bool:
        if not user32:
            return False
        # WHEEL_DELTA is 120 per click
        amount = clicks * 120
        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, amount, 0)
        return True


class NativeWindowsKeyboard(KeyboardController):
    """Direct Unicode and virtual key keyboard synthesis."""

    def type_text(self, text: str) -> bool:
        if not user32:
            return False
        for char in text:
            code = ord(char)
            # Send keydown unicode
            user32.keybd_event(0, code, KEYEVENTF_UNICODE, 0)
            time.sleep(0.01)
            # Send keyup unicode
            user32.keybd_event(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0)
            time.sleep(0.01)
        return True

    def press_key(self, key_name: str) -> bool:
        if not user32:
            return False
        key = key_name.lower().strip()
        vk = VK_MAP.get(key)
        if vk is None and len(key) == 1:
            vk = ord(key.upper())

        if vk is not None:
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            return True
        return False

    def hotkey(self, *keys: str) -> bool:
        if not user32 or not keys:
            return False
        vk_list = []
        for k in keys:
            k_lower = k.lower().strip()
            vk = VK_MAP.get(k_lower)
            if vk is None and len(k_lower) == 1:
                vk = ord(k_lower.upper())
            if vk is not None:
                vk_list.append(vk)

        # Press all in sequence
        for vk in vk_list:
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.02)

        time.sleep(0.05)

        # Release in reverse sequence
        for vk in reversed(vk_list):
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.02)

        return True


class NativeWindowsScreen(ScreenCapture):
    """Full-desktop screen capture using Pillow ImageGrab with resolution querying."""

    def get_resolution(self) -> ScreenResolution:
        if user32:
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            return ScreenResolution(width=w, height=h)
        return ScreenResolution(width=1920, height=1080)

    def capture(self, output_path: Optional[str] = None) -> bytes:
        from io import BytesIO
        from PIL import ImageGrab

        # Capture primary or all monitors
        image = ImageGrab.grab(all_screens=True)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

        if output_path:
            p = Path(output_path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "wb") as f:
                f.write(image_bytes)
            logger.info(f"Captured screenshot to: {p}")

        return image_bytes
