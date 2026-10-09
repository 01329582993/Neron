"""Unified Activation Coordinator — bridges Global Hotkeys (Shift+L) and Voice Wake-Word ('Hey Neron')."""

from __future__ import annotations

import sys
import threading
from typing import Callable, Optional

from neron.config.manager import ConfigManager
from neron.os.windows.hotkey import GlobalHotkeyListener, bring_console_to_front
from neron.utils.logger import get_logger
from neron.voice.listener import BackgroundVoiceListener
from neron.voice.text_to_speech.engine import SystemTTSEngine

logger = get_logger("core.activation")


class ActivationCoordinator:
    """
    Coordinates multi-modal activation for Neron:
    1. Global Keyboard Hotkey (Shift+L)
    2. Background Microphone Wake Word ('Hey Neron' or 'Neron')
    """

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        on_activate: Optional[Callable[[str], None]] = None,
        enable_tts_feedback: bool = True,
    ):
        self.config_manager = config_manager or ConfigManager()
        self.on_activate = on_activate
        self.enable_tts_feedback = enable_tts_feedback

        self.hotkey_listener = GlobalHotkeyListener()
        self.voice_listener = BackgroundVoiceListener(
            wake_phrases=["neron", "hey neron"],
            on_wake=self._on_voice_wake,
        )
        self.tts = SystemTTSEngine()
        self._is_active = False
        self._lock = threading.Lock()

    def start(self) -> bool:
        """Start both hotkey and voice background listeners."""
        with self._lock:
            if self._is_active:
                return True

            # 1. Register Shift+L hotkey
            shortcut = getattr(self.config_manager.config.security, "activation_shortcut", "shift+l")
            self.hotkey_listener.register(shortcut, self._on_hotkey_pressed)
            self.hotkey_listener.start()

            # 2. Start Background Voice Listener
            self.voice_listener.start()

            self._is_active = True
            logger.info("ActivationCoordinator started. Listening for 'Shift+L' and voice 'Neron'.")
            return True

    def stop(self) -> None:
        """Stop all background listeners."""
        with self._lock:
            if not self._is_active:
                return

            self.hotkey_listener.stop()
            self.voice_listener.stop()
            self._is_active = False
            logger.info("ActivationCoordinator stopped.")

    def is_active(self) -> bool:
        return self._is_active

    def trigger_activation(self, source: str = "manual") -> None:
        """Programmatically trigger activation."""
        self._handle_activation(source)

    def _on_hotkey_pressed(self) -> None:
        logger.info("⌨️ Global Hotkey Shift+L pressed! Activating Neron.")
        self._handle_activation("hotkey")

    def _on_voice_wake(self, phrase: str) -> None:
        logger.info(f"🎤 Voice call detected: '{phrase}'! Activating Neron.")
        self._handle_activation("voice")

    def _handle_activation(self, source: str) -> None:
        """Core activation handler: restores window, provides audio feedback, dispatches event."""
        # 1. Bring Neron window to the foreground
        bring_console_to_front()

        # 2. Audio chime / spoken greeting if enabled
        if self.enable_tts_feedback:
            try:
                # Play brief chime or spoken confirmation
                if sys.platform.startswith("win"):
                    import winsound
                    # Crisp two-tone wake chime (800Hz then 1200Hz)
                    winsound.Beep(880, 80)
                    winsound.Beep(1320, 100)
            except Exception:
                pass

        # 3. Notify external subscriber / REPL
        if self.on_activate:
            try:
                self.on_activate(source)
            except Exception as e:
                logger.error(f"Error in on_activate callback: {e}")
