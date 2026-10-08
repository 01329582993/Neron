"""Linux-specific implementation of the OSController interface."""

import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

from neron.os.base import OSController, ProcessInfo, SystemTelemetry, WindowInfo
from neron.utils.logger import get_logger

logger = get_logger("os.linux")


class LinuxController(OSController):
    """Native Linux operating system controller."""

    def get_platform_name(self) -> str:
        return "linux"

    def get_telemetry(self) -> SystemTelemetry:
        """Query real-time hardware telemetry on Linux."""
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        battery = psutil.sensors_battery()
        boot_time = psutil.boot_time()

        return SystemTelemetry(
            os_name="Linux",
            os_version=f"{platform.system()} {platform.release()} ({platform.machine()})",
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
        """Launch application using Linux shell."""
        common_apps = {
            "chrome": "google-chrome",
            "google chrome": "google-chrome",
            "firefox": "firefox",
            "code": "code",
            "vs code": "code",
            "terminal": "gnome-terminal",
            "files": "nautilus",
            "calculator": "gnome-calculator",
        }
        target = common_apps.get(app_name.lower().strip(), app_name)
        cmd = [target] + (args or [])

        try:
            subprocess.Popen(
                cmd,
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
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
        """Query foreground window via xdotool if available."""
        res = self.execute_terminal_command("xdotool getactivewindow getwindowname", timeout=2)
        if res["exit_code"] == 0 and res["stdout"]:
            return WindowInfo(
                window_id="active",
                title=res["stdout"],
                is_active=True,
            )
        return None

    def list_windows(self) -> List[WindowInfo]:
        """List open windows using wmctrl if available."""
        res = self.execute_terminal_command("wmctrl -l", timeout=3)
        windows: List[WindowInfo] = []
        if res["exit_code"] == 0 and res["stdout"]:
            for line in res["stdout"].splitlines():
                parts = line.split(maxsplit=3)
                if len(parts) >= 4:
                    windows.append(
                        WindowInfo(
                            window_id=parts[0],
                            title=parts[3],
                            is_active=False,
                        )
                    )
        return windows

    def open_path_in_file_manager(self, path: str) -> bool:
        """Open native file manager with xdg-open."""
        resolved = Path(path).resolve()
        if not resolved.exists():
            logger.warning(f"Path does not exist: {resolved}")
            return False
        res = self.execute_terminal_command(f"xdg-open '{resolved}'", timeout=5)
        return res["exit_code"] == 0

    def execute_terminal_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Execute command in bash."""
        start_time = time.time()
        try:
            completed = subprocess.run(
                ["bash", "-c", command],
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
        """Query system audio volume via amixer."""
        res = self.execute_terminal_command("amixer get Master", timeout=3)
        if res["exit_code"] == 0 and res["stdout"]:
            import re
            match = re.search(r"\[(\d+)%\]", res["stdout"])
            if match:
                return int(match.group(1))
        return None

    def set_volume(self, level: int) -> bool:
        """Set system audio volume using amixer."""
        level = max(0, min(100, level))
        res = self.execute_terminal_command(f"amixer set Master {level}%", timeout=3)
        return res["exit_code"] == 0
