"""Windows Global Hotkey Listener — registers system-wide keyboard shortcuts."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
import threading
import time
from typing import Callable, Dict, Optional

from neron.utils.logger import get_logger

logger = get_logger("os.windows.hotkey")

# Virtual key constants and modifier masks
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001
SW_RESTORE = 9

VK_MAP: Dict[str, int] = {
    "l": 0x4C,
    "n": 0x4E,
    "space": 0x20,
    "enter": 0x0D,
    "escape": 0x1B,
    "tab": 0x09,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
}


def parse_shortcut(shortcut_str: str) -> tuple[int, int]:
    """Parse shortcut string (e.g. 'shift+l' or 'ctrl+alt+n') into (modifiers, vk_code)."""
    parts = [p.strip().lower() for p in shortcut_str.split("+")]
    modifiers = 0
    vk = 0

    for part in parts:
        if part in ("shift", "s"):
            modifiers |= MOD_SHIFT
        elif part in ("ctrl", "control", "c"):
            modifiers |= MOD_CONTROL
        elif part in ("alt", "a"):
            modifiers |= MOD_ALT
        elif part in ("win", "windows", "w", "super"):
            modifiers |= MOD_WIN
        else:
            # Key part
            if part in VK_MAP:
                vk = VK_MAP[part]
            elif len(part) == 1:
                vk = ord(part.upper())
            else:
                logger.warning(f"Unrecognized key token in shortcut: '{part}'")

    return modifiers, vk


def bring_console_to_front() -> bool:
    """Bring the active Neron console window to the foreground."""
    if not sys.platform.startswith("win"):
        return False

    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            return True

        # Fallback: search visible windows with 'Neron' in title
        length = 256
        buff = ctypes.create_unicode_buffer(length)
        fg_hwnd = user32.GetForegroundWindow()

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        found_hwnd = [None]

        def callback(h, extra):
            if user32.IsWindowVisible(h):
                user32.GetWindowTextW(h, buff, length)
                if "neron" in buff.value.lower():
                    found_hwnd[0] = h
                    return False
            return True

        user32.EnumWindows(EnumWindowsProc(callback), 0)
        if found_hwnd[0]:
            user32.ShowWindow(found_hwnd[0], SW_RESTORE)
            user32.SetForegroundWindow(found_hwnd[0])
            return True

        return False
    except Exception as e:
        logger.error(f"Failed to bring console window to front: {e}")
        return False


class GlobalHotkeyListener:
    """
    Listens for system-wide keyboard shortcuts in a background daemon thread.
    Zero third-party dependencies — uses native Windows User32 RegisterHotKey.
    """

    def __init__(self):
        self._callbacks: Dict[int, Callable[[], None]] = {}
        self._shortcut_defs: Dict[int, tuple[int, int, str]] = {}
        self._next_id = 100
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._is_running = False

    def register(self, shortcut: str, callback: Callable[[], None]) -> int:
        """Register a shortcut string (e.g. 'shift+l') with a callback."""
        with self._lock:
            hotkey_id = self._next_id
            self._next_id += 1
            mods, vk = parse_shortcut(shortcut)
            self._callbacks[hotkey_id] = callback
            self._shortcut_defs[hotkey_id] = (mods, vk, shortcut)
            logger.info(f"Registered hotkey handler id={hotkey_id} for '{shortcut}'")
            return hotkey_id

    def unregister(self, hotkey_id: int) -> None:
        """Unregister a hotkey by its ID."""
        with self._lock:
            self._callbacks.pop(hotkey_id, None)
            self._shortcut_defs.pop(hotkey_id, None)

    def start(self) -> bool:
        """Start listening for registered hotkeys in the background."""
        if not sys.platform.startswith("win"):
            logger.warning("GlobalHotkeyListener is only natively supported on Windows.")
            return False

        if self._is_running:
            return True

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="neron-hotkey-listener", daemon=True)
        self._thread.start()
        self._is_running = True
        logger.info("GlobalHotkeyListener started.")
        return True

    def stop(self) -> None:
        """Stop listening and cleanly unregister all hotkeys."""
        self._stop_event.set()
        self._is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("GlobalHotkeyListener stopped.")

    def is_running(self) -> bool:
        return self._is_running

    def _run_loop(self) -> None:
        """Internal Win32 message pump for WM_HOTKEY."""
        user32 = ctypes.windll.user32
        registered_ids = []

        try:
            # Register hotkeys on this thread
            with self._lock:
                for hid, (mods, vk, sc_str) in self._shortcut_defs.items():
                    res = user32.RegisterHotKey(None, hid, mods, vk)
                    if res:
                        registered_ids.append(hid)
                        logger.info(f"Active Windows global hotkey '{sc_str}' (id={hid})")
                    else:
                        err = ctypes.GetLastError()
                        logger.warning(f"Could not register hotkey '{sc_str}' (Win32 error: {err})")

            msg = wintypes.MSG()
            while not self._stop_event.is_set():
                # Check for WM_HOTKEY message
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    if msg.message == WM_HOTKEY:
                        hid = msg.wParam
                        with self._lock:
                            cb = self._callbacks.get(hid)
                        if cb:
                            try:
                                cb()
                            except Exception as e:
                                logger.error(f"Error executing callback for hotkey id={hid}: {e}")
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                time.sleep(0.04)

        finally:
            # Unregister all hotkeys registered on this thread
            for hid in registered_ids:
                user32.UnregisterHotKey(None, hid)
            logger.debug("Unregistered all active hotkeys.")
