"""macOS-specific architecture-ready implementation of OSController."""

import platform
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

from neron.os.base import OSController, ProcessInfo, SystemTelemetry, WindowInfo
from neron.utils.logger import get_logger

logger = get_logger("os.macos")


class MacOSController(OSController):
    """Architecture-ready macOS controller."""

    def get_platform_name(self) -> str:
        return "macos"

    def get_telemetry(self) -> SystemTelemetry:
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        battery = psutil.sensors_battery()
        boot_time = psutil.boot_time()

        return SystemTelemetry(
            os_name="macOS",
            os_version=f"macOS {platform.mac_ver()[0]}",
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
        query = name.lower()
        return [p for p in self.list_processes() if query in p.name.lower()]

    def kill_process(self, pid: int) -> bool:
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            proc.wait(timeout=3)
            return True
        except Exception:
            return False

    def open_application(self, app_name: str, args: Optional[List[str]] = None) -> bool:
        cmd = ["open", "-a", app_name]
        if args:
            cmd.extend(["--args"] + args)
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            logger.error(f"Failed to open '{app_name}': {e}")
            return False

    def close_application(self, app_name: str) -> bool:
        script = f'tell application "{app_name}" to quit'
        res = self.execute_terminal_command(f"osascript -e '{script}'", timeout=5)
        return res["exit_code"] == 0

    def get_active_window(self) -> Optional[WindowInfo]:
        script = 'tell application "System Events" to get name of first application process whose frontmost is true'
        res = self.execute_terminal_command(f"osascript -e '{script}'", timeout=3)
        if res["exit_code"] == 0 and res["stdout"]:
            return WindowInfo(window_id="active", title=res["stdout"], is_active=True)
        return None

    def list_windows(self) -> List[WindowInfo]:
        return []

    def open_path_in_file_manager(self, path: str) -> bool:
        resolved = Path(path).resolve()
        res = self.execute_terminal_command(f"open '{resolved}'", timeout=3)
        return res["exit_code"] == 0

    def execute_terminal_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        start_time = time.time()
        try:
            completed = subprocess.run(
                ["bash", "-c", command],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "exit_code": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
                "duration_ms": round((time.time() - start_time) * 1000, 2),
                "timed_out": False,
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": "Command timed out",
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
        res = self.execute_terminal_command("osascript -e 'output volume of (get volume settings)'", timeout=3)
        if res["exit_code"] == 0 and res["stdout"].isdigit():
            return int(res["stdout"])
        return None

    def set_volume(self, level: int) -> bool:
        level = max(0, min(100, level))
        res = self.execute_terminal_command(f"osascript -e 'set volume output volume {level}'", timeout=3)
        return res["exit_code"] == 0
