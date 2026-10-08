"""Self-diagnostics and system health manager — Stage 12.

Provides:
- HealthCheckResult       : Structured result dataclass (name, status, details, hint)
- HardwareCapabilityReport: Aggregated hardware profiling result
- HealthManager           : Runs every check and returns actionable results
- run_cli_diagnostics()   : Plain-text renderer for `neron --diagnose`
"""

from __future__ import annotations

import importlib
import platform
import requests
import shutil
import socket
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from neron.config.manager import ConfigManager
from neron.os.base import get_os_controller
from neron.utils.logger import get_logger

logger = get_logger("diagnostics.health")


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

STATUS_HEALTHY = "HEALTHY"
STATUS_WARNING = "WARNING"
STATUS_DEGRADED = "DEGRADED"
STATUS_FAILED = "FAILED"


@dataclass
class HealthCheckResult:
    """Structured result for one diagnostic check."""
    name: str
    status: str  # HEALTHY | WARNING | DEGRADED | FAILED
    details: str
    remediation_hint: Optional[str] = None

    @property
    def is_ok(self) -> bool:
        return self.status == STATUS_HEALTHY

    @property
    def badge(self) -> str:
        mapping = {
            STATUS_HEALTHY: "[OK]",
            STATUS_WARNING: "[WARN]",
            STATUS_DEGRADED: "[DEGRADED]",
            STATUS_FAILED: "[FAIL]",
        }
        return mapping.get(self.status, "[?]")


@dataclass
class HardwareCapabilityReport:
    """Aggregated hardware profile evaluated once at startup."""
    cpu_cores: int = 0
    cpu_logical: int = 0
    cpu_model: str = "Unknown"
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0
    disk_free_gb: float = 0.0
    gpu_available: bool = False
    gpu_names: List[str] = field(default_factory=list)
    tier: str = "MINIMAL"          # MINIMAL | STANDARD | PERFORMANCE | HIGH_END

    def to_dict(self) -> Dict:
        return {
            "cpu_cores": self.cpu_cores,
            "cpu_logical": self.cpu_logical,
            "cpu_model": self.cpu_model,
            "ram_total_gb": self.ram_total_gb,
            "ram_available_gb": self.ram_available_gb,
            "disk_free_gb": self.disk_free_gb,
            "gpu_available": self.gpu_available,
            "gpu_names": self.gpu_names,
            "tier": self.tier,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Required Python packages per subsystem
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_PACKAGES: Dict[str, str] = {
    "psutil": "System telemetry (CPU, RAM, disk, processes)",
    "yaml": "Configuration file parsing (PyYAML)",
    "requests": "HTTP client for Ollama and web integrations",
    "rich": "Desktop console and UI rendering",
}

OPTIONAL_PACKAGES: Dict[str, str] = {
    "sounddevice": "Voice input/output",
    "numpy": "Audio processing and vision DSP",
    "PIL": "Screen capture (Pillow)",
    "cv2": "Computer vision element detection (OpenCV)",
    "mss": "High-performance screen capture",
    "bs4": "Web content extraction (BeautifulSoup)",
    "faster_whisper": "Local speech-to-text (faster-whisper)",
}


# ─────────────────────────────────────────────────────────────────────────────
# HealthManager
# ─────────────────────────────────────────────────────────────────────────────

class HealthManager:
    """
    Performs comprehensive environment and subsystem self-diagnostics.

    Usage::

        manager = HealthManager()
        results = manager.run_full_diagnostics()
        hardware = manager.evaluate_hardware()
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config_manager = config_manager or ConfigManager()
        self._hardware_report: Optional[HardwareCapabilityReport] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def run_full_diagnostics(self) -> List[HealthCheckResult]:
        """Execute all diagnostics and return a structured list of results."""
        results: List[HealthCheckResult] = [
            self.check_python_environment(),
            self.check_core_dependencies(),
            self.check_optional_dependencies(),
            self.check_os_controller(),
            self.check_storage_and_directories(),
            self.check_hardware_capabilities(),
            self.check_local_ai_endpoint(),
            self.check_network_latency(),
            self.check_audio_subsystem(),
        ]
        return results

    def evaluate_hardware(self) -> HardwareCapabilityReport:
        """Return a cached hardware capability profile."""
        if self._hardware_report is not None:
            return self._hardware_report
        self._hardware_report = self._build_hardware_report()
        return self._hardware_report

    # ── Individual checks ─────────────────────────────────────────────────────

    def check_python_environment(self) -> HealthCheckResult:
        """Check Python runtime version."""
        v = sys.version_info
        ver_str = f"{v.major}.{v.minor}.{v.micro}"
        plat_str = f"{platform.system()} {platform.release()} ({platform.machine()})"
        if v.major < 3 or (v.major == 3 and v.minor < 10):
            return HealthCheckResult(
                name="Python Runtime",
                status=STATUS_FAILED,
                details=f"Python {ver_str} on {plat_str} — Python 3.10+ required.",
                remediation_hint="Upgrade your Python installation to 3.10 or newer from python.org.",
            )
        return HealthCheckResult(
            name="Python Runtime",
            status=STATUS_HEALTHY,
            details=f"Python {ver_str} on {plat_str}",
        )

    def check_core_dependencies(self) -> HealthCheckResult:
        """Verify all required Python packages are importable."""
        missing = []
        for pkg, purpose in REQUIRED_PACKAGES.items():
            try:
                importlib.import_module(pkg)
            except ImportError:
                missing.append((pkg, purpose))

        if missing:
            names = ", ".join(p for p, _ in missing)
            hints = "; ".join(f"pip install {p}" for p, _ in missing)
            return HealthCheckResult(
                name="Core Dependencies",
                status=STATUS_FAILED,
                details=f"Missing required packages: {names}",
                remediation_hint=f"Install them via: {hints}",
            )
        return HealthCheckResult(
            name="Core Dependencies",
            status=STATUS_HEALTHY,
            details=f"All {len(REQUIRED_PACKAGES)} required packages present.",
        )

    def check_optional_dependencies(self) -> HealthCheckResult:
        """Verify optional packages and report which subsystems are degraded."""
        missing = []
        for pkg, purpose in OPTIONAL_PACKAGES.items():
            try:
                importlib.import_module(pkg)
            except ImportError:
                missing.append((pkg, purpose))

        if not missing:
            return HealthCheckResult(
                name="Optional Dependencies",
                status=STATUS_HEALTHY,
                details=f"All {len(OPTIONAL_PACKAGES)} optional packages present. Full capability mode.",
            )

        # Only warn; Neron degrades gracefully
        degraded_features = "; ".join(f"{p} ({desc})" for p, desc in missing)
        names = ", ".join(p for p, _ in missing)
        return HealthCheckResult(
            name="Optional Dependencies",
            status=STATUS_WARNING,
            details=f"Missing optional packages: {names}. Affected: {degraded_features}.",
            remediation_hint=f"Install with: pip install {' '.join(p for p, _ in missing)}",
        )

    def check_os_controller(self) -> HealthCheckResult:
        """Verify OS abstraction layer and system telemetry."""
        try:
            ctrl = get_os_controller()
            telemetry = ctrl.get_telemetry()
            return HealthCheckResult(
                name="OS Abstraction Layer",
                status=STATUS_HEALTHY,
                details=(
                    f"Platform: {ctrl.get_platform_name()} | "
                    f"CPU: {telemetry.cpu_percent:.1f}% | "
                    f"RAM: {telemetry.memory_used_gb:.1f}/{telemetry.memory_total_gb:.1f} GB "
                    f"({telemetry.memory_percent:.0f}%)"
                ),
            )
        except Exception as e:
            return HealthCheckResult(
                name="OS Abstraction Layer",
                status=STATUS_FAILED,
                details=f"Failed to query OS controller: {e}",
                remediation_hint="Ensure psutil is installed: pip install psutil",
            )

    def check_storage_and_directories(self) -> HealthCheckResult:
        """Verify workspace storage and writable runtime directories."""
        cfg = self.config_manager.config
        try:
            data_dir = Path(cfg.system.data_dir).resolve()
            logs_dir = Path(cfg.system.logs_dir).resolve()
            data_dir.mkdir(parents=True, exist_ok=True)
            logs_dir.mkdir(parents=True, exist_ok=True)

            # Write-ability test
            test_file = data_dir / ".neron_write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()

            # Disk space check on data_dir partition
            usage = shutil.disk_usage(data_dir)
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)

            if free_gb < 0.5:
                return HealthCheckResult(
                    name="Storage & Directories",
                    status=STATUS_FAILED,
                    details=f"Critical: Only {free_gb:.1f} GB free on data partition ({total_gb:.0f} GB total).",
                    remediation_hint="Free at least 500 MB of disk space to continue.",
                )
            if free_gb < 2.0:
                return HealthCheckResult(
                    name="Storage & Directories",
                    status=STATUS_WARNING,
                    details=f"Low disk space: {free_gb:.1f} GB free (recommend >2 GB). Directories writable.",
                    remediation_hint="Consider freeing disk space for model and cache storage.",
                )
            return HealthCheckResult(
                name="Storage & Directories",
                status=STATUS_HEALTHY,
                details=f"Directories writable. Disk: {free_gb:.1f} GB free / {total_gb:.0f} GB total.",
            )
        except Exception as e:
            return HealthCheckResult(
                name="Storage & Directories",
                status=STATUS_FAILED,
                details=f"Storage check failed: {e}",
                remediation_hint="Verify user write permissions for the project directory.",
            )

    def check_hardware_capabilities(self) -> HealthCheckResult:
        """Evaluate CPU, RAM, and GPU and return a capability tier."""
        try:
            report = self.evaluate_hardware()
            tier_desc = {
                "MINIMAL": "Minimal — basic text features only (no real-time vision/voice).",
                "STANDARD": "Standard — offline LLM and voice capable.",
                "PERFORMANCE": "Performance — suitable for mid-size local models.",
                "HIGH_END": "High-end — full local AI, large models, vision at full speed.",
            }.get(report.tier, report.tier)

            gpu_str = (
                f"GPU(s): {', '.join(report.gpu_names)}" if report.gpu_available
                else "No CUDA/ROCm GPU detected (CPU inference mode)"
            )
            details = (
                f"CPU: {report.cpu_model} ({report.cpu_cores}P/{report.cpu_logical}L cores) | "
                f"RAM: {report.ram_total_gb:.1f} GB total, {report.ram_available_gb:.1f} GB free | "
                f"{gpu_str} | Tier: {report.tier} — {tier_desc}"
            )

            status = STATUS_HEALTHY if report.tier in ("STANDARD", "PERFORMANCE", "HIGH_END") else STATUS_WARNING
            hint = None
            if report.tier == "MINIMAL":
                hint = (
                    "Your hardware meets minimum requirements but may struggle with large models. "
                    "Consider using tiny quantized models (e.g., ollama pull tinyllama)."
                )

            return HealthCheckResult(
                name="Hardware Capabilities",
                status=status,
                details=details,
                remediation_hint=hint,
            )
        except Exception as e:
            return HealthCheckResult(
                name="Hardware Capabilities",
                status=STATUS_FAILED,
                details=f"Hardware evaluation failed: {e}",
                remediation_hint="Ensure psutil is installed.",
            )

    def check_local_ai_endpoint(self) -> HealthCheckResult:
        """Check connectivity to the local Ollama inference server."""
        ollama_cfg = self.config_manager.config.ai.ollama
        try:
            resp = requests.get(f"{ollama_cfg.host}/api/tags", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "?") for m in data.get("models", [])]
                if models:
                    return HealthCheckResult(
                        name="Local AI Endpoint (Ollama)",
                        status=STATUS_HEALTHY,
                        details=f"Ollama at {ollama_cfg.host} — {len(models)} model(s): {', '.join(models[:4])}",
                    )
                return HealthCheckResult(
                    name="Local AI Endpoint (Ollama)",
                    status=STATUS_WARNING,
                    details=f"Ollama running at {ollama_cfg.host}, but no models downloaded.",
                    remediation_hint=f"Run: ollama pull {ollama_cfg.model}",
                )
            return HealthCheckResult(
                name="Local AI Endpoint (Ollama)",
                status=STATUS_WARNING,
                details=f"Ollama server returned HTTP {resp.status_code}.",
                remediation_hint="Check Ollama service logs.",
            )
        except ImportError:
            return HealthCheckResult(
                name="Local AI Endpoint (Ollama)",
                status=STATUS_FAILED,
                details="requests library is not installed.",
                remediation_hint="pip install requests",
            )
        except Exception:
            return HealthCheckResult(
                name="Local AI Endpoint (Ollama)",
                status=STATUS_DEGRADED,
                details=f"No Ollama server at {ollama_cfg.host}. Operating in offline heuristic mode.",
                remediation_hint="Start Ollama with 'ollama serve' or install it from https://ollama.ai",
            )

    def check_network_latency(self) -> HealthCheckResult:
        """Probe public network latency to evaluate online integration quality."""
        try:
            targets = [("8.8.8.8", 53), ("1.1.1.1", 53)]
            latencies = []
            for host, port in targets:
                try:
                    t0 = time.monotonic()
                    s = socket.create_connection((host, port), timeout=2)
                    s.close()
                    latencies.append((time.monotonic() - t0) * 1000)
                except OSError:
                    pass

            if not latencies:
                return HealthCheckResult(
                    name="Network Latency",
                    status=STATUS_DEGRADED,
                    details="No public internet connectivity detected. Online tools unavailable.",
                    remediation_hint="Check your network connection or firewall settings.",
                )

            avg_ms = sum(latencies) / len(latencies)
            if avg_ms < 100:
                status = STATUS_HEALTHY
                label = "excellent"
            elif avg_ms < 300:
                status = STATUS_HEALTHY
                label = "good"
            elif avg_ms < 600:
                status = STATUS_WARNING
                label = "high latency"
            else:
                status = STATUS_DEGRADED
                label = "very high latency"

            return HealthCheckResult(
                name="Network Latency",
                status=status,
                details=f"Average public DNS latency: {avg_ms:.0f}ms ({label}). Online tools operational.",
                remediation_hint="Consider wired connection for lower latency." if avg_ms >= 300 else None,
            )
        except Exception as e:
            return HealthCheckResult(
                name="Network Latency",
                status=STATUS_DEGRADED,
                details=f"Network probe failed: {e}",
            )

    def check_audio_subsystem(self) -> HealthCheckResult:
        """Check voice audio input/output availability."""
        if not self.config_manager.config.voice.enabled:
            return HealthCheckResult(
                name="Voice Subsystem",
                status=STATUS_HEALTHY,
                details="Voice mode disabled in config — console/text mode active.",
            )
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devs = [d for d in devices if d.get("max_input_channels", 0) > 0]
            output_devs = [d for d in devices if d.get("max_output_channels", 0) > 0]
            if not input_devs:
                return HealthCheckResult(
                    name="Voice Subsystem",
                    status=STATUS_WARNING,
                    details="No microphone/input device detected. STT unavailable.",
                    remediation_hint="Connect a microphone and check OS audio permissions.",
                )
            return HealthCheckResult(
                name="Voice Subsystem",
                status=STATUS_HEALTHY,
                details=(
                    f"{len(input_devs)} input device(s), {len(output_devs)} output device(s) found. "
                    f"Default input: {sd.query_devices(kind='input')['name']}"
                ),
            )
        except ImportError:
            return HealthCheckResult(
                name="Voice Subsystem",
                status=STATUS_WARNING,
                details="Voice dependencies (sounddevice) not installed.",
                remediation_hint="pip install sounddevice numpy",
            )
        except Exception as e:
            return HealthCheckResult(
                name="Voice Subsystem",
                status=STATUS_FAILED,
                details=f"Audio query failed: {e}",
                remediation_hint="Check OS microphone permissions and audio driver.",
            )

    # ── Hardware profiling ────────────────────────────────────────────────────

    def _build_hardware_report(self) -> HardwareCapabilityReport:
        """Probe hardware and return a HardwareCapabilityReport."""
        report = HardwareCapabilityReport()
        try:
            import psutil
            report.cpu_cores = psutil.cpu_count(logical=False) or 1
            report.cpu_logical = psutil.cpu_count(logical=True) or 1
            mem = psutil.virtual_memory()
            report.ram_total_gb = mem.total / (1024 ** 3)
            report.ram_available_gb = mem.available / (1024 ** 3)
        except ImportError:
            pass

        # CPU model name
        try:
            report.cpu_model = platform.processor() or "Unknown CPU"
        except Exception:
            report.cpu_model = "Unknown CPU"

        # GPU detection — NVIDIA via pynvml, then torch fallback
        try:
            import pynvml  # type: ignore
            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            for i in range(count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode()
                report.gpu_names.append(name)
            report.gpu_available = count > 0
            pynvml.nvmlShutdown()
        except Exception:
            pass

        if not report.gpu_available:
            try:
                import torch  # type: ignore
                if torch.cuda.is_available():
                    report.gpu_available = True
                    for i in range(torch.cuda.device_count()):
                        report.gpu_names.append(torch.cuda.get_device_name(i))
            except Exception:
                pass

        # Determine capability tier
        report.tier = self._classify_tier(report)
        return report

    @staticmethod
    def _classify_tier(r: HardwareCapabilityReport) -> str:
        """Classify hardware into a capability tier."""
        if r.gpu_available and r.ram_total_gb >= 16 and r.cpu_cores >= 8:
            return "HIGH_END"
        if r.ram_total_gb >= 12 and r.cpu_cores >= 4:
            return "PERFORMANCE"
        if r.ram_total_gb >= 6 and r.cpu_cores >= 2:
            return "STANDARD"
        return "MINIMAL"

    # ── Summary helpers ───────────────────────────────────────────────────────

    def overall_status(self, results: List[HealthCheckResult]) -> str:
        """Summarise a list of results to a single overall status string."""
        statuses = {r.status for r in results}
        if STATUS_FAILED in statuses:
            return STATUS_FAILED
        if STATUS_DEGRADED in statuses:
            return STATUS_DEGRADED
        if STATUS_WARNING in statuses:
            return STATUS_WARNING
        return STATUS_HEALTHY


# ─────────────────────────────────────────────────────────────────────────────
# CLI renderer (plain text — no Rich dependency)
# ─────────────────────────────────────────────────────────────────────────────

def run_cli_diagnostics(config_manager: Optional[ConfigManager] = None) -> None:
    """Plain-text diagnostic renderer for `neron --diagnose`."""
    print("=" * 60)
    print("               NERON SYSTEM DIAGNOSTICS")
    print("=" * 60)

    manager = HealthManager(config_manager=config_manager)
    results = manager.run_full_diagnostics()

    for res in results:
        print(f"\n{res.badge} {res.name}")
        print(f"   Status : {res.status}")
        print(f"   Details: {res.details}")
        if res.remediation_hint:
            print(f"   Fix    : {res.remediation_hint}")

    overall = manager.overall_status(results)
    print("\n" + "=" * 60)
    print(f"  Overall Status: {overall}")
    print("=" * 60 + "\n")

    # Hardware summary block
    hw = manager.evaluate_hardware()
    print("── Hardware Profile ──────────────────────────────────────")
    print(f"  CPU   : {hw.cpu_model} ({hw.cpu_cores} physical / {hw.cpu_logical} logical cores)")
    print(f"  RAM   : {hw.ram_total_gb:.1f} GB total / {hw.ram_available_gb:.1f} GB free")
    if hw.gpu_available:
        print(f"  GPU   : {', '.join(hw.gpu_names)}")
    else:
        print("  GPU   : None detected (CPU inference mode)")
    print(f"  Tier  : {hw.tier}")
    print("─" * 60)
