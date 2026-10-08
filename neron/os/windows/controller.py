"""Windows-specific implementation of the OSController interface."""

import ctypes
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

from neron.os.base import OSController, ProcessInfo, SystemTelemetry, WindowInfo
from neron.utils.logger import get_logger

logger = get_logger("os.windows")


class WindowsController(OSController):
    """Native Windows operating system controller."""

    def __init__(self):
        self._user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None

    def get_platform_name(self) -> str:
        return "windows"

    def get_telemetry(self) -> SystemTelemetry:
        """Query real-time hardware telemetry."""
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(str(Path.home().drive or "C:"))
        battery = psutil.sensors_battery()
        boot_time = psutil.boot_time()

        return SystemTelemetry(
            os_name="Windows",
            os_version=f"{platform.system()} {platform.release()} (Build {platform.version()})",
            cpu_percent=psutil.cpu_percent(interval=None),
            cpu_count=psutil.cpu_count(logical=True) or 1,
            memory_total_gb=round(mem.total / (1024 ** 3), 2),
            memory_used_gb=round(mem.used / (1024 ** 3), 2),
            memory_percent=mem.percent,
            disk_total_gb=round(disk.total / (1024 ** 3), 2),
            disk_free_gb=round(disk.free / (1024 ** 3), 2),
            disk_percent=disk.percent,
            battery_percent=battery.percent if battery else None,
            is_charging=battery.power_plugged if battery else None,
            uptime_seconds=time.time() - boot_time,
        )

    def list_processes(self) -> List[ProcessInfo]:
        """List running processes."""
        processes: List[ProcessInfo] = []
        for proc in psutil.process_iter(["pid", "name", "status"]):
            try:
                info = proc.info
                processes.append(
                    ProcessInfo(
                        pid=info["pid"],
                        name=info["name"] or "unknown",
                        status=info["status"] or "unknown",
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return processes

    def find_process(self, name: str) -> List[ProcessInfo]:
        """Find processes matching name substring."""
        query = name.lower()
        results: List[ProcessInfo] = []
        for p in self.list_processes():
            if query in p.name.lower():
                results.append(p)
        return results

    def kill_process(self, pid: int) -> bool:
        """Terminate a process by PID."""
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            proc.wait(timeout=3)
            return True
        except psutil.TimeoutExpired:
            proc.kill()
            return True
        except Exception as e:
            logger.error(f"Failed to kill process {pid}: {e}")
            return False

    def open_application(self, app_name: str, args: Optional[List[str]] = None) -> bool:
        """Launch application using native Windows shell."""
        # Common aliases mapping
        common_apps = {
            "chrome": "chrome",
            "google chrome": "chrome",
            "edge": "msedge",
            "firefox": "firefox",
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "code": "code",
            "vs code": "code",
            "terminal": "wt.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "explorer": "explorer.exe",
        }
        target = common_apps.get(app_name.lower().strip(), app_name)
        cmd = [target] + (args or [])

        try:
            subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            logger.info(f"Launched application '{app_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to launch '{app_name}': {e}")
            return False

    def close_application(self, app_name: str) -> bool:
        """Close processes matching application name."""
        targets = self.find_process(app_name)
        if not targets:
            logger.warning(f"No running processes found matching '{app_name}'")
            return False

        closed_any = False
        for p in targets:
            if self.kill_process(p.pid):
                closed_any = True
        return closed_any

    def get_active_window(self) -> Optional[WindowInfo]:
        """Query foreground window title and info via User32."""
        if not self._user32:
            return None

        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            return None

        length = self._user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return WindowInfo(window_id=str(hwnd), title="", is_active=True)

        buff = ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value

        # Query process ID associated with hwnd
        pid = ctypes.c_ulong()
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc_name = None
        try:
            proc_name = psutil.Process(pid.value).name()
        except Exception:
            pass

        return WindowInfo(
            window_id=str(hwnd),
            title=title,
            process_name=proc_name,
            is_active=True
        )

    def list_windows(self) -> List[WindowInfo]:
        """Enumerate visible desktop windows."""
        if not self._user32:
            return []

        windows: List[WindowInfo] = []

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd, extra):
            if self._user32.IsWindowVisible(hwnd):
                length = self._user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    self._user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.strip()
                    if title:
                        pid = ctypes.c_ulong()
                        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        proc_name = None
                        try:
                            proc_name = psutil.Process(pid.value).name()
                        except Exception:
                            pass
                        windows.append(
                            WindowInfo(
                                window_id=str(hwnd),
                                title=title,
                                process_name=proc_name,
                                is_active=False
                            )
                        )
            return True

        self._user32.EnumWindows(EnumWindowsProc(callback), 0)
        return windows

    def open_path_in_file_manager(self, path: str) -> bool:
        """Open Windows Explorer for target directory."""
        resolved = Path(path).resolve()
        if not resolved.exists():
            logger.warning(f"Path does not exist: {resolved}")
            return False
        try:
            os.startfile(str(resolved))
            return True
        except Exception as e:
            logger.error(f"Failed to open path {path}: {e}")
            return False

    def execute_terminal_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Execute command in PowerShell/cmd."""
        start_time = time.time()
        try:
            # Use PowerShell for rich execution
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = (time.time() - start_time) * 1000
            return {
                "exit_code": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
                "duration_ms": round(duration, 2),
                "timed_out": False,
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds.",
                "duration_ms": timeout * 1000,
                "timed_out": True,
            }
        except Exception as e:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "duration_ms": 0.0,
                "timed_out": False,
            }

    def get_volume(self) -> Optional[int]:
        """Query system audio volume via PowerShell."""
        # Simple non-blocking PowerShell query
        res = self.execute_terminal_command(
            "[int]((Get-AudioDevice -PlaybackVolume 2>$null) -replace '%','')",
            timeout=5
        )
        if res["exit_code"] == 0 and res["stdout"].isdigit():
            return int(res["stdout"])
        return None

    def set_volume(self, level: int) -> bool:
        """Set system audio volume (0-100)."""
        level = max(0, min(100, level))
        # Use nircmd or PowerShell if available
        res = self.execute_terminal_command(
            f"Set-AudioDevice -PlaybackVolume {level} 2>$null",
            timeout=5
        )
        return res["exit_code"] == 0
