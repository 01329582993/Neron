"""Native operating system speech synthesis engine."""

import platform
import subprocess
from typing import Optional
from neron.os.base import OSController, get_os_controller
from neron.voice.base import TTSEngine
from neron.utils.logger import get_logger

logger = get_logger("voice.tts")


class SystemTTSEngine(TTSEngine):
    """Zero-dependency Text-to-Speech using native operating system speech synthesis."""

    def __init__(self, os_controller: Optional[OSController] = None):
        self.os_controller = os_controller or get_os_controller()
        self.platform_name = self.os_controller.get_platform_name()

    def is_available(self) -> bool:
        """Check if native speech synthesizer is accessible."""
        if self.platform_name == "windows":
            return True
        elif self.platform_name == "macos":
            res = self.os_controller.execute_terminal_command("which say", timeout=2)
            return res["exit_code"] == 0
        elif self.platform_name == "linux":
            res = self.os_controller.execute_terminal_command("which spd-say || which espeak", timeout=2)
            return res["exit_code"] == 0
        return False

    def speak(self, text: str) -> bool:
        """Synthesize and play audio through speakers non-blockingly."""
        clean_text = text.replace('"', '\\"').replace("'", "\\'").strip()
        if not clean_text:
            return True

        logger.debug(f"Speaking: '{clean_text[:60]}...'")

        if self.platform_name == "windows":
            # Native Windows SAPI speech synthesis
            ps_cmd = (
                f"Add-Type -AssemblyName System.Speech; "
                f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$s.Speak('{clean_text}')"
            )
            res = self.os_controller.execute_terminal_command(ps_cmd, timeout=15)
            return res["exit_code"] == 0

        elif self.platform_name == "macos":
            res = self.os_controller.execute_terminal_command(f'say "{clean_text}"', timeout=15)
            return res["exit_code"] == 0

        elif self.platform_name == "linux":
            # Try spd-say then espeak
            res = self.os_controller.execute_terminal_command(f'spd-say "{clean_text}" || espeak "{clean_text}"', timeout=15)
            return res["exit_code"] == 0

        return False
