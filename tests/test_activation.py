"""Tests for Global Hotkey (Shift+L), Voice Wake-Word ('Hey Neron'), and Windows Autostart."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from neron.os.windows.hotkey import (
    GlobalHotkeyListener,
    parse_shortcut,
    MOD_SHIFT,
    MOD_CONTROL,
    MOD_ALT,
)
from neron.voice.listener import BackgroundVoiceListener
from neron.core.activation import ActivationCoordinator
from neron.os.windows.autostart import WindowsAutostart


class TestShortcutParsing:
    def test_parse_shift_l(self):
        mods, vk = parse_shortcut("shift+l")
        assert mods & MOD_SHIFT != 0
        assert vk == 0x4C  # 'L'

    def test_parse_ctrl_alt_n(self):
        mods, vk = parse_shortcut("ctrl+alt+n")
        assert mods & MOD_CONTROL != 0
        assert mods & MOD_ALT != 0
        assert vk == 0x4E  # 'N'

    def test_case_insensitive(self):
        mods1, vk1 = parse_shortcut("SHIFT+L")
        mods2, vk2 = parse_shortcut("shift+l")
        assert (mods1, vk1) == (mods2, vk2)


class TestGlobalHotkeyListener:
    def test_register_and_unregister(self):
        listener = GlobalHotkeyListener()
        called = []

        hid = listener.register("shift+l", lambda: called.append(True))
        assert hid >= 100
        assert hid in listener._callbacks

        listener.unregister(hid)
        assert hid not in listener._callbacks

    def test_listener_lifecycle(self):
        listener = GlobalHotkeyListener()
        listener.register("shift+l", lambda: None)

        with patch("neron.os.windows.hotkey.sys.platform", "win32"):
            with patch("ctypes.windll.user32.RegisterHotKey", return_value=True):
                with patch("ctypes.windll.user32.UnregisterHotKey", return_value=True):
                    ok = listener.start()
                    assert ok is True
                    assert listener.is_running() is True
                    listener.stop()
                    assert listener.is_running() is False


class TestBackgroundVoiceListener:
    def test_init_and_phrases(self):
        listener = BackgroundVoiceListener(wake_phrases=["neron", "hey neron"])
        assert "neron" in listener.wake_phrases
        assert "hey neron" in listener.wake_phrases

    def test_simulate_wake_triggers_callback(self):
        detected = []
        listener = BackgroundVoiceListener(
            wake_phrases=["neron"],
            on_wake=lambda phrase: detected.append(phrase),
        )
        listener.simulate_wake("neron")
        assert detected == ["neron"]

    def test_lifecycle_stop(self):
        listener = BackgroundVoiceListener()
        listener._is_listening = True
        listener.stop()
        assert listener.is_listening() is False


class TestActivationCoordinator:
    def test_activation_callback_triggered(self):
        events = []
        coordinator = ActivationCoordinator(
            on_activate=lambda src: events.append(src),
            enable_tts_feedback=False,
        )

        coordinator.trigger_activation("hotkey")
        assert events == ["hotkey"]

        coordinator.trigger_activation("voice")
        assert events == ["hotkey", "voice"]

    def test_start_and_stop_lifecycle(self):
        coordinator = ActivationCoordinator(enable_tts_feedback=False)
        with patch.object(coordinator.hotkey_listener, "start", return_value=True):
            with patch.object(coordinator.voice_listener, "start", return_value=True):
                ok = coordinator.start()
                assert ok is True
                assert coordinator.is_active() is True

                coordinator.stop()
                assert coordinator.is_active() is False


class TestWindowsAutostart:
    def test_enable_and_disable(self, tmp_path):
        autostart = WindowsAutostart(launcher_name="TestNeron.bat")
        autostart.startup_dir = tmp_path

        assert autostart.is_enabled() is False

        ok = autostart.enable(background_mode=True, repo_root=tmp_path)
        assert ok is True
        assert autostart.is_enabled() is True

        content = autostart.get_launcher_path().read_text(encoding="utf-8")
        assert "python" in content.lower()
        assert "--listen" in content

        disabled = autostart.disable()
        assert disabled is True
        assert autostart.is_enabled() is False
