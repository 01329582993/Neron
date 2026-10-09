"""Windows Autostart Manager — enables or disables Neron launching on Windows boot."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Optional

from neron.utils.logger import get_logger

logger = get_logger("os.windows.autostart")


class WindowsAutostart:
    """
    Manages automated launching of Neron when Windows starts up.
    Uses the Windows user Startup directory (%APPDATA%\\...\\Startup) which requires
    no administrator privileges and is transparent and safe.
    """

    def __init__(self, launcher_name: str = "NeronAssistant.bat"):
        self.launcher_name = launcher_name
        self.startup_dir = self.get_startup_directory()

    @staticmethod
    def get_startup_directory() -> Path:
        """Resolve the Windows user Startup folder path."""
        appdata = os.environ.get("APPDATA")
        if appdata:
            p = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            if p.is_dir():
                return p

        # Fallback
        return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

    def get_launcher_path(self) -> Path:
        return self.startup_dir / self.launcher_name

    def is_enabled(self) -> bool:
        """Check if Neron is configured to launch on Windows startup."""
        return self.get_launcher_path().exists()

    def enable(self, background_mode: bool = True, repo_root: Optional[Path] = None) -> bool:
        """
        Create the Windows startup launcher script.
        
        Args:
            background_mode: If True, launches Neron with --listen in the background.
            repo_root: Path to the Neron workspace (defaults to current working directory).
        """
        try:
            target_dir = self.startup_dir
            target_dir.mkdir(parents=True, exist_ok=True)

            root = (repo_root or Path.cwd()).resolve()
            python_exe = sys.executable

            # Script that changes directory to project root and runs Neron in listening mode
            mode_flag = "--listen" if background_mode else ""
            script_content = (
                f"@echo off\r\n"
                f"cd /d \"{root}\"\r\n"
                f"start \"\" \"{python_exe}\" -m neron {mode_flag}\r\n"
            )

            launcher_path = self.get_launcher_path()
            launcher_path.write_text(script_content, encoding="utf-8")
            logger.info(f"Enabled Windows startup auto-launch: {launcher_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to enable Windows autostart: {e}")
            return False

    def disable(self) -> bool:
        """Remove the Windows startup launcher script."""
        try:
            launcher_path = self.get_launcher_path()
            if launcher_path.exists():
                launcher_path.unlink()
                logger.info(f"Disabled Windows startup auto-launch: {launcher_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to disable Windows autostart: {e}")
            return False
