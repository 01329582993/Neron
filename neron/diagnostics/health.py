"""Self-diagnostics and system health manager."""

from dataclasses import dataclass
from pathlib import Path
import platform
import sys
from typing import List, Optional
import requests

from neron.config.manager import ConfigManager
from neron.os.base import get_os_controller
from neron.utils.logger import get_logger

logger = get_logger("diagnostics.health")


@dataclass
class HealthCheckResult:
    name: str
    status: str  # "HEALTHY", "WARNING", "DEGRADED", "FAILED"
    details: str
    remediation_hint: Optional[str] = None


class HealthManager:
    """Performs deep environmental and subsystem self-diagnostics."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config_manager = config_manager or ConfigManager()

    def run_full_diagnostics(self) -> List[HealthCheckResult]:
        """Execute all diagnostics and return structured results."""
        results: List[HealthCheckResult] = []
        results.append(self.check_python_environment())
        results.append(self.check_os_controller())
        results.append(self.check_storage_and_directories())
        results.append(self.check_local_ai_endpoint())
        results.append(self.check_audio_subsystem())
        return results

    def check_python_environment(self) -> HealthCheckResult:
        """Check Python runtime version and dependencies."""
        v = sys.version_info
        ver_str = f"{v.major}.{v.minor}.{v.micro}"
        if v.major < 3 or (v.major == 3 and v.minor < 10):
            return HealthCheckResult(
                name="Python Runtime",
                status="FAILED",
                details=f"Current version is {ver_str}. Python 3.10+ is required.",
                remediation_hint="Upgrade your Python installation to 3.10 or newer."
            )
        return HealthCheckResult(
            name="Python Runtime",
            status="HEALTHY",
            details=f"Python {ver_str} on {platform.system()} ({platform.machine()})"
        )

    def check_os_controller(self) -> HealthCheckResult:
        """Verify operating system abstraction integration."""
        try:
            ctrl = get_os_controller()
            telemetry = ctrl.get_telemetry()
            return HealthCheckResult(
                name="OS Abstraction Layer",
                status="HEALTHY",
                details=(
                    f"Platform: {ctrl.get_platform_name()} | CPU: {telemetry.cpu_percent}% | "
                    f"RAM: {telemetry.memory_used_gb}/{telemetry.memory_total_gb} GB ({telemetry.memory_percent}%)"
                )
            )
        except Exception as e:
            return HealthCheckResult(
                name="OS Abstraction Layer",
                status="FAILED",
                details=f"Failed to query OS controller: {e}",
                remediation_hint="Ensure psutil is installed and you have sufficient user privileges."
            )

    def check_storage_and_directories(self) -> HealthCheckResult:
        """Verify workspace storage and writable runtime directories."""
        cfg = self.config_manager.config
        try:
            data_dir = Path(cfg.system.data_dir).resolve()
            logs_dir = Path(cfg.system.logs_dir).resolve()
            data_dir.mkdir(parents=True, exist_ok=True)
            logs_dir.mkdir(parents=True, exist_ok=True)

            # Test write ability
            test_file = data_dir / ".write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()

            return HealthCheckResult(
                name="Storage & Directories",
                status="HEALTHY",
                details=f"Directories writable (Data: {data_dir}, Logs: {logs_dir})"
            )
        except Exception as e:
            return HealthCheckResult(
                name="Storage & Directories",
                status="FAILED",
                details=f"Directory write test failed: {e}",
                remediation_hint="Verify user write permissions for the project directory."
            )

    def check_local_ai_endpoint(self) -> HealthCheckResult:
        """Check connectivity to local inference endpoints (Ollama)."""
        ollama_cfg = self.config_manager.config.ai.ollama
        try:
            resp = requests.get(f"{ollama_cfg.host}/api/tags", timeout=2)
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                if models:
                    return HealthCheckResult(
                        name="Local AI Endpoint (Ollama)",
                        status="HEALTHY",
                        details=f"Connected to {ollama_cfg.host}. Installed models: {', '.join(models[:4])}"
                    )
                else:
                    return HealthCheckResult(
                        name="Local AI Endpoint (Ollama)",
                        status="WARNING",
                        details=f"Ollama running at {ollama_cfg.host}, but no models are downloaded.",
                        remediation_hint=f"Run: ollama pull {ollama_cfg.model}"
                    )
            return HealthCheckResult(
                name="Local AI Endpoint (Ollama)",
                status="WARNING",
                details=f"Server returned HTTP {resp.status_code}",
                remediation_hint="Check your Ollama service logs."
            )
        except Exception:
            return HealthCheckResult(
                name="Local AI Endpoint (Ollama)",
                status="DEGRADED",
                details=f"No server responding at {ollama_cfg.host}. Neron is operating in offline heuristic mode.",
                remediation_hint="Start Ollama by running 'ollama serve' or keep using offline heuristic rules."
            )

    def check_audio_subsystem(self) -> HealthCheckResult:
        """Check voice audio input/output availability."""
        if not self.config_manager.config.voice.enabled:
            return HealthCheckResult(
                name="Voice Subsystem",
                status="HEALTHY",
                details="Voice mode is disabled in configuration. Text/Console mode active."
            )
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            return HealthCheckResult(
                name="Voice Subsystem",
                status="HEALTHY",
                details=f"Found {len(devices)} audio device(s)."
            )
        except ImportError:
            return HealthCheckResult(
                name="Voice Subsystem",
                status="WARNING",
                details="Voice dependencies (sounddevice/pyaudio) not installed.",
                remediation_hint="Run: pip install sounddevice numpy to enable voice mode."
            )
        except Exception as e:
            return HealthCheckResult(
                name="Voice Subsystem",
                status="FAILED",
                details=f"Audio query failed: {e}",
                remediation_hint="Check OS microphone permissions."
            )
