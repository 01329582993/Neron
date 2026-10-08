"""Abstract base class and models for Operating System abstraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import sys
from typing import Any, Dict, List, Optional


@dataclass
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    status: str = "running"


@dataclass
class WindowInfo:
    window_id: str
    title: str
    process_name: Optional[str] = None
    is_active: bool = False


@dataclass
class SystemTelemetry:
    os_name: str
    os_version: str
    cpu_percent: float
    cpu_count: int
    memory_total_gb: float
    memory_used_gb: float
    memory_percent: float
    disk_total_gb: float
    disk_free_gb: float
    disk_percent: float
    battery_percent: Optional[float] = None
    is_charging: Optional[bool] = None
    uptime_seconds: float = 0.0


class OSController(ABC):
    """Abstract interface defining all operating system interactions."""

    @abstractmethod
    def get_platform_name(self) -> str:
        """Return the canonical platform name ('windows', 'linux', 'macos')."""
        pass

    @abstractmethod
    def get_telemetry(self) -> SystemTelemetry:
        """Query real-time CPU, RAM, disk, and battery telemetry."""
        pass

    @abstractmethod
    def list_processes(self) -> List[ProcessInfo]:
        """List running user/system processes."""
        pass

    @abstractmethod
    def find_process(self, name: str) -> List[ProcessInfo]:
        """Find processes matching name query."""
        pass

    @abstractmethod
    def kill_process(self, pid: int) -> bool:
        """Terminate a process by PID."""
        pass

    @abstractmethod
    def open_application(self, app_name: str, args: Optional[List[str]] = None) -> bool:
        """Launch an application by executable name or registered command."""
        pass

    @abstractmethod
    def close_application(self, app_name: str) -> bool:
        """Gracefully or forcefully close an application."""
        pass

    @abstractmethod
    def get_active_window(self) -> Optional[WindowInfo]:
        """Get currently focused foreground window."""
        pass

    @abstractmethod
    def list_windows(self) -> List[WindowInfo]:
        """List all visible open windows."""
        pass

    @abstractmethod
    def open_path_in_file_manager(self, path: str) -> bool:
        """Open the native file manager showing the target directory/file."""
        pass

    @abstractmethod
    def execute_terminal_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Execute a shell command with timeout, capturing stdout, stderr, and exit code."""
        pass

    @abstractmethod
    def get_volume(self) -> Optional[int]:
        """Query system audio volume (0-100)."""
        pass

    @abstractmethod
    def set_volume(self, level: int) -> bool:
        """Set system audio volume (0-100)."""
        pass


def get_os_controller() -> OSController:
    """Factory creating the appropriate concrete OSController for current platform."""
    if sys.platform.startswith("win"):
        from neron.os.windows.controller import WindowsController
        return WindowsController()
    elif sys.platform.startswith("linux"):
        from neron.os.linux.controller import LinuxController
        return LinuxController()
    elif sys.platform == "darwin":
        from neron.os.macos.controller import MacOSController
        return MacOSController()
    else:
        # Fallback to linux-like generic POSIX
        from neron.os.linux.controller import LinuxController
        return LinuxController()
