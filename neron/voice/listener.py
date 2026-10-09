"""Background Voice Listener — detects wake phrases ('Hey Neron', 'Neron') continuously."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from typing import Callable, List, Optional

from neron.utils.logger import get_logger
from neron.voice.base import WakeWordEngine
from neron.voice.wake_word.engine import SimpleWakeWordDetector

logger = get_logger("voice.listener")


class BackgroundVoiceListener:
    """
    Continuous background microphone listener for wake word / activation phrase.
    On Windows, uses native SpeechRecognitionEngine via lightweight sub-process
    with zero third-party dependencies.
    """

    def __init__(
        self,
        wake_phrases: Optional[List[str]] = None,
        on_wake: Optional[Callable[[str], None]] = None,
        wake_engine: Optional[WakeWordEngine] = None,
    ):
        self.wake_phrases = [p.lower().strip() for p in (wake_phrases or ["neron", "hey neron"])]
        self.on_wake = on_wake
        self.wake_engine = wake_engine or SimpleWakeWordDetector()
        self._thread: Optional[threading.Thread] = None
        self._process: Optional[subprocess.Popen] = None
        self._stop_event = threading.Event()
        self._is_listening = False
        self._lock = threading.Lock()

    def start(self) -> bool:
        """Start listening for the wake phrase in the background."""
        if self._is_listening:
            return True

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_native_listener if sys.platform.startswith("win") else self._run_generic_listener,
            name="neron-voice-listener",
            daemon=True,
        )
        self._thread.start()
        self._is_listening = True
        logger.info(f"BackgroundVoiceListener started (phrases={self.wake_phrases}).")
        return True

    def stop(self) -> None:
        """Stop background microphone listening."""
        self._stop_event.set()
        self._is_listening = False

        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=1.0)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        logger.info("BackgroundVoiceListener stopped.")

    def is_listening(self) -> bool:
        return self._is_listening

    def simulate_wake(self, phrase: str = "neron") -> None:
        """Helper for automated testing or manual trigger."""
        if self.on_wake:
            self.on_wake(phrase)

    def _run_native_listener(self) -> None:
        """Native Windows speech listener using System.Speech.Recognition."""
        # Build PowerShell script with embedded recognition loop
        escaped_phrases = ", ".join(f"'{p}'" for p in self.wake_phrases)
        ps_script = f"""
        Add-Type -AssemblyName System.Speech;
        $rec = New-Object System.Speech.Recognition.SpeechRecognitionEngine;
        try {{
            $rec.SetInputToDefaultAudioDevice();
        }} catch {{
            Write-Output "AUDIO_ERROR";
            exit 1;
        }}
        $choices = New-Object System.Speech.Recognition.Choices;
        $choices.Add(@({escaped_phrases}));
        $gb = New-Object System.Speech.Recognition.GrammarBuilder($choices);
        $g = New-Object System.Speech.Recognition.Grammar($gb);
        $rec.LoadGrammar($g);

        while ($true) {{
            $result = $rec.Recognize();
            if ($result -ne $null -and $result.Confidence -ge 0.4) {{
                Write-Output ("WAKE:" + $result.Text);
            }}
        }}
        """

        try:
            self._process = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            while not self._stop_event.is_set():
                if self._process.poll() is not None:
                    # Process died, wait briefly and break
                    break

                line = self._process.stdout.readline() if self._process.stdout else ""
                if not line:
                    time.sleep(0.05)
                    continue

                line_str = line.strip()
                if line_str.startswith("WAKE:"):
                    detected = line_str.replace("WAKE:", "").strip().lower()
                    logger.info(f"🎤 Wake phrase detected by microphone: '{detected}'")
                    if self.on_wake:
                        try:
                            self.on_wake(detected)
                        except Exception as e:
                            logger.error(f"Error in on_wake callback: {e}")
                elif "AUDIO_ERROR" in line_str:
                    logger.warning("Default audio input device is unavailable for voice listening.")
                    break

        except Exception as e:
            logger.error(f"Error in native voice listener: {e}")
        finally:
            self._is_listening = False

    def _run_generic_listener(self) -> None:
        """Fallback listener loop for non-Windows or simulated environments."""
        while not self._stop_event.is_set():
            time.sleep(0.2)
