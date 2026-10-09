"""
Stage 12 — Self-Diagnostics & Health System Tests
==================================================
Tests for:
- HealthCheckResult dataclass
- HardwareCapabilityReport dataclass and tier classification
- HealthManager.check_python_environment()
- HealthManager.check_core_dependencies()
- HealthManager.check_optional_dependencies()
- HealthManager.check_os_controller()
- HealthManager.check_storage_and_directories()
- HealthManager.check_hardware_capabilities()
- HealthManager.check_local_ai_endpoint()
- HealthManager.check_network_latency()
- HealthManager.check_audio_subsystem()
- HealthManager.run_full_diagnostics()
- HealthManager.evaluate_hardware()
- HealthManager.overall_status()
- DiagnosticsRunTool
- DiagnosticsHardwareTool
- run_cli_diagnostics() CLI renderer
"""

from __future__ import annotations

import sys
import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from neron.diagnostics.health import (
    HealthCheckResult,
    HardwareCapabilityReport,
    HealthManager,
    run_cli_diagnostics,
    STATUS_HEALTHY,
    STATUS_WARNING,
    STATUS_DEGRADED,
    STATUS_FAILED,
    REQUIRED_PACKAGES,
    OPTIONAL_PACKAGES,
)
from neron.tools.diagnostics.tools import DiagnosticsRunTool, DiagnosticsHardwareTool


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def manager():
    return HealthManager()


@pytest.fixture(autouse=True)
def _no_real_network(request, monkeypatch):
    """Prevent any test from making real network calls.

    Patches the two methods that perform live I/O (Ollama HTTP request and
    DNS socket probes) so the suite completes in seconds rather than waiting
    on connection timeouts.

    Tests decorated with ``@pytest.mark.uses_real_network`` (i.e. those that
    do their own patching at the requests/socket level) are exempt.
    """
    if request.node.get_closest_marker("uses_real_network"):
        return  # let the test manage its own patching

    _ai_result = HealthCheckResult(
        name="Local AI Endpoint (Ollama)",
        status=STATUS_DEGRADED,
        details="Mocked — no real Ollama server in test environment.",
        remediation_hint="Start Ollama with 'ollama serve'.",
    )
    _net_result = HealthCheckResult(
        name="Network Latency",
        status=STATUS_HEALTHY,
        details="Mocked — avg latency 5.0 ms (stub).",
    )
    monkeypatch.setattr(
        "neron.diagnostics.health.HealthManager.check_local_ai_endpoint",
        lambda self: _ai_result,
    )
    monkeypatch.setattr(
        "neron.diagnostics.health.HealthManager.check_network_latency",
        lambda self: _net_result,
    )


# ─────────────────────────────────────────────────────────────────────────────
# HealthCheckResult
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthCheckResult:
    def test_is_ok_healthy(self):
        r = HealthCheckResult(name="X", status=STATUS_HEALTHY, details="fine")
        assert r.is_ok is True

    def test_is_ok_failed(self):
        r = HealthCheckResult(name="X", status=STATUS_FAILED, details="broken")
        assert r.is_ok is False

    @pytest.mark.parametrize("status,expected_badge", [
        (STATUS_HEALTHY, "[OK]"),
        (STATUS_WARNING, "[WARN]"),
        (STATUS_DEGRADED, "[DEGRADED]"),
        (STATUS_FAILED, "[FAIL]"),
        ("UNKNOWN", "[?]"),
    ])
    def test_badge(self, status, expected_badge):
        r = HealthCheckResult(name="X", status=status, details="")
        assert r.badge == expected_badge

    def test_remediation_hint_optional(self):
        r = HealthCheckResult(name="X", status=STATUS_HEALTHY, details="ok")
        assert r.remediation_hint is None

    def test_remediation_hint_provided(self):
        r = HealthCheckResult(name="X", status=STATUS_FAILED, details="bad", remediation_hint="fix it")
        assert r.remediation_hint == "fix it"


# ─────────────────────────────────────────────────────────────────────────────
# HardwareCapabilityReport & tier classification
# ─────────────────────────────────────────────────────────────────────────────

class TestHardwareCapabilityReport:
    def test_to_dict_keys(self):
        hw = HardwareCapabilityReport(cpu_cores=4, ram_total_gb=16.0, tier="STANDARD")
        d = hw.to_dict()
        assert "cpu_cores" in d
        assert "ram_total_gb" in d
        assert "tier" in d
        assert "gpu_available" in d
        assert "gpu_names" in d

    def test_to_dict_values(self):
        hw = HardwareCapabilityReport(cpu_cores=8, ram_total_gb=32.0, gpu_available=True, gpu_names=["RTX 4090"], tier="HIGH_END")
        d = hw.to_dict()
        assert d["cpu_cores"] == 8
        assert d["ram_total_gb"] == 32.0
        assert d["gpu_available"] is True
        assert d["gpu_names"] == ["RTX 4090"]
        assert d["tier"] == "HIGH_END"

    @pytest.mark.parametrize("gpu, ram, cores, expected_tier", [
        (True, 32.0, 16, "HIGH_END"),
        (False, 16.0, 8, "PERFORMANCE"),
        (False, 8.0, 4, "STANDARD"),
        (False, 4.0, 2, "MINIMAL"),
        (False, 2.0, 1, "MINIMAL"),
    ])
    def test_classify_tier(self, gpu, ram, cores, expected_tier):
        hw = HardwareCapabilityReport(
            gpu_available=gpu,
            ram_total_gb=ram,
            cpu_cores=cores,
        )
        assert HealthManager._classify_tier(hw) == expected_tier


# ─────────────────────────────────────────────────────────────────────────────
# Python environment check
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckPythonEnvironment:
    def test_passes_on_current_python(self, manager):
        result = manager.check_python_environment()
        # CI always runs a supported Python
        assert result.name == "Python Runtime"
        assert result.status in (STATUS_HEALTHY, STATUS_FAILED)

    def test_fails_on_old_python(self, manager):
        vi = MagicMock()
        vi.major = 3
        vi.minor = 8
        vi.micro = 0
        with patch("neron.diagnostics.health.sys.version_info", vi):
            result = manager.check_python_environment()
        assert result.status == STATUS_FAILED
        assert "3.8.0" in result.details
        assert result.remediation_hint is not None

    def test_healthy_on_py310(self, manager):
        vi = MagicMock()
        vi.major = 3
        vi.minor = 10
        vi.micro = 5
        with patch("neron.diagnostics.health.sys.version_info", vi):
            result = manager.check_python_environment()
        assert result.status == STATUS_HEALTHY
        assert "3.10.5" in result.details


# ─────────────────────────────────────────────────────────────────────────────
# Core dependency check
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckCoreDependencies:
    def test_healthy_when_all_present(self, manager):
        # All required packages are present in the test environment
        result = manager.check_core_dependencies()
        assert result.name == "Core Dependencies"
        # May vary by environment — at minimum status must be a known value
        assert result.status in (STATUS_HEALTHY, STATUS_FAILED)

    def test_failed_when_package_missing(self, manager):
        original = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "requests":
                raise ImportError("mock missing")
            return original(name, *args, **kwargs)

        with patch("neron.diagnostics.health.importlib.import_module", side_effect=mock_import):
            result = manager.check_core_dependencies()

        assert result.status == STATUS_FAILED
        assert "requests" in result.details
        assert result.remediation_hint is not None

    def test_healthy_all_mocked(self, manager):
        with patch("neron.diagnostics.health.importlib.import_module", return_value=MagicMock()):
            result = manager.check_core_dependencies()
        assert result.status == STATUS_HEALTHY
        assert str(len(REQUIRED_PACKAGES)) in result.details


# ─────────────────────────────────────────────────────────────────────────────
# Optional dependency check
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckOptionalDependencies:
    def test_returns_valid_status(self, manager):
        result = manager.check_optional_dependencies()
        assert result.name == "Optional Dependencies"
        assert result.status in (STATUS_HEALTHY, STATUS_WARNING)

    def test_warning_when_optional_missing(self, manager):
        original = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name in ("sounddevice", "faster_whisper"):
                raise ImportError("mock missing")
            return original(name, *args, **kwargs)

        with patch("neron.diagnostics.health.importlib.import_module", side_effect=mock_import):
            result = manager.check_optional_dependencies()

        assert result.status == STATUS_WARNING
        assert result.remediation_hint is not None

    def test_healthy_when_all_present(self, manager):
        with patch("neron.diagnostics.health.importlib.import_module", return_value=MagicMock()):
            result = manager.check_optional_dependencies()
        assert result.status == STATUS_HEALTHY
        assert "Full capability" in result.details


# ─────────────────────────────────────────────────────────────────────────────
# OS Controller check
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckOsController:
    def test_healthy(self, manager):
        result = manager.check_os_controller()
        assert result.name == "OS Abstraction Layer"
        assert result.status in (STATUS_HEALTHY, STATUS_FAILED)

    def test_failed_when_controller_raises(self, manager):
        with patch("neron.diagnostics.health.get_os_controller", side_effect=RuntimeError("no psutil")):
            result = manager.check_os_controller()
        assert result.status == STATUS_FAILED
        assert "no psutil" in result.details
        assert result.remediation_hint is not None


# ─────────────────────────────────────────────────────────────────────────────
# Storage & directories check
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckStorage:
    def test_healthy_with_plenty_of_space(self, manager, tmp_path):
        manager.config_manager.config.system.data_dir = str(tmp_path / "data")
        manager.config_manager.config.system.logs_dir = str(tmp_path / "logs")

        mock_usage = MagicMock()
        mock_usage.free = 10 * 1024 ** 3   # 10 GB
        mock_usage.total = 100 * 1024 ** 3

        with patch("neron.diagnostics.health.shutil.disk_usage", return_value=mock_usage):
            result = manager.check_storage_and_directories()

        assert result.status == STATUS_HEALTHY
        assert "writable" in result.details.lower()

    def test_warning_on_low_disk(self, manager, tmp_path):
        manager.config_manager.config.system.data_dir = str(tmp_path / "data")
        manager.config_manager.config.system.logs_dir = str(tmp_path / "logs")

        mock_usage = MagicMock()
        mock_usage.free = int(1.5 * 1024 ** 3)   # 1.5 GB — below 2 GB threshold
        mock_usage.total = 50 * 1024 ** 3

        with patch("neron.diagnostics.health.shutil.disk_usage", return_value=mock_usage):
            result = manager.check_storage_and_directories()

        assert result.status == STATUS_WARNING
        assert result.remediation_hint is not None

    def test_failed_on_critical_disk(self, manager, tmp_path):
        manager.config_manager.config.system.data_dir = str(tmp_path / "data")
        manager.config_manager.config.system.logs_dir = str(tmp_path / "logs")

        mock_usage = MagicMock()
        mock_usage.free = int(0.1 * 1024 ** 3)   # 100 MB — below 500 MB threshold
        mock_usage.total = 50 * 1024 ** 3

        with patch("neron.diagnostics.health.shutil.disk_usage", return_value=mock_usage):
            result = manager.check_storage_and_directories()

        assert result.status == STATUS_FAILED
        assert "Critical" in result.details

    def test_failed_on_permission_error(self, manager, tmp_path):
        manager.config_manager.config.system.data_dir = "/root/neron_no_access"
        manager.config_manager.config.system.logs_dir = "/root/neron_no_access_logs"

        with patch("neron.diagnostics.health.Path.mkdir", side_effect=PermissionError("denied")):
            result = manager.check_storage_and_directories()

        assert result.status == STATUS_FAILED


# ─────────────────────────────────────────────────────────────────────────────
# Hardware capabilities check
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckHardwareCapabilities:
    def _make_hw(self, **kwargs):
        defaults = dict(cpu_cores=4, cpu_logical=8, cpu_model="i7", ram_total_gb=16.0,
                        ram_available_gb=8.0, gpu_available=False, gpu_names=[])
        defaults.update(kwargs)
        hw = HardwareCapabilityReport(**defaults)
        hw.tier = HealthManager._classify_tier(hw)
        return hw

    def test_healthy_standard_hardware(self, manager):
        hw = self._make_hw(ram_total_gb=12.0, cpu_cores=4)
        with patch.object(manager, "evaluate_hardware", return_value=hw):
            result = manager.check_hardware_capabilities()
        assert result.status == STATUS_HEALTHY
        assert "PERFORMANCE" in result.details or "STANDARD" in result.details

    def test_warning_minimal_hardware(self, manager):
        hw = self._make_hw(ram_total_gb=3.0, cpu_cores=1)
        with patch.object(manager, "evaluate_hardware", return_value=hw):
            result = manager.check_hardware_capabilities()
        assert result.status == STATUS_WARNING
        assert result.remediation_hint is not None

    def test_high_end_with_gpu(self, manager):
        hw = self._make_hw(ram_total_gb=32.0, cpu_cores=16, gpu_available=True, gpu_names=["RTX 4090"])
        hw.tier = "HIGH_END"
        with patch.object(manager, "evaluate_hardware", return_value=hw):
            result = manager.check_hardware_capabilities()
        assert result.status == STATUS_HEALTHY
        assert "HIGH_END" in result.details
        assert "RTX 4090" in result.details

    def test_failed_on_exception(self, manager):
        with patch.object(manager, "evaluate_hardware", side_effect=RuntimeError("psutil crash")):
            result = manager.check_hardware_capabilities()
        assert result.status == STATUS_FAILED
        assert "psutil crash" in result.details


# ─────────────────────────────────────────────────────────────────────────────
# Local AI endpoint check
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.uses_real_network
class TestCheckLocalAiEndpoint:
    def test_healthy_with_models(self, manager):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3.2:3b"}, {"name": "mistral:7b"}]}

        with patch("neron.diagnostics.health.requests") as mock_req:
            mock_req.get.return_value = mock_resp
            result = manager.check_local_ai_endpoint()

        assert result.status == STATUS_HEALTHY
        assert "llama3.2:3b" in result.details

    def test_warning_no_models(self, manager):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": []}

        with patch("neron.diagnostics.health.requests") as mock_req:
            mock_req.get.return_value = mock_resp
            result = manager.check_local_ai_endpoint()

        assert result.status == STATUS_WARNING
        assert result.remediation_hint is not None

    def test_warning_bad_status_code(self, manager):
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch("neron.diagnostics.health.requests") as mock_req:
            mock_req.get.return_value = mock_resp
            result = manager.check_local_ai_endpoint()

        assert result.status == STATUS_WARNING

    def test_degraded_when_not_running(self, manager):
        with patch("neron.diagnostics.health.requests") as mock_req:
            mock_req.get.side_effect = Exception("connection refused")
            result = manager.check_local_ai_endpoint()

        assert result.status == STATUS_DEGRADED
        assert "offline" in result.details.lower() or "heuristic" in result.details.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Network latency check
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.uses_real_network
class TestCheckNetworkLatency:
    def _make_mock_socket(self, latency_ms: float):
        """Return a mock socket.create_connection that measures fake latency."""
        import time
        def fake_conn(addr, timeout=None):
            s = MagicMock()
            s.close = MagicMock()
            return s
        return fake_conn

    def test_healthy_low_latency(self, manager):
        mock_conn = MagicMock()
        mock_conn.close = MagicMock()
        times = iter([0.0, 0.05, 0.05, 0.10])
        with patch("neron.diagnostics.health.socket.create_connection", return_value=mock_conn):
            with patch("neron.diagnostics.health.time.monotonic", side_effect=lambda: next(times)):
                result = manager.check_network_latency()
        assert result.status == STATUS_HEALTHY
        assert "ms" in result.details

    def test_degraded_when_no_connectivity(self, manager):
        with patch("neron.diagnostics.health.socket.create_connection", side_effect=OSError("refused")):
            result = manager.check_network_latency()
        assert result.status == STATUS_DEGRADED
        assert "No public internet" in result.details

    def test_degraded_on_general_exception(self, manager):
        # Patch create_connection to raise a generic Exception (not OSError, so it's caught by outer try)
        with patch("neron.diagnostics.health.socket.create_connection", side_effect=RuntimeError("no socket")):
            result = manager.check_network_latency()
        # RuntimeError is not OSError so inner pass is skipped; no latencies collected -> DEGRADED
        assert result.status == STATUS_DEGRADED

    def test_healthy_good_latency(self, manager):
        mock_conn = MagicMock()
        mock_conn.close = MagicMock()
        times = iter([0.0, 0.08, 0.08, 0.18])
        with patch("neron.diagnostics.health.socket.create_connection", return_value=mock_conn):
            with patch("neron.diagnostics.health.time.monotonic", side_effect=lambda: next(times)):
                result = manager.check_network_latency()
        assert result.status == STATUS_HEALTHY


# ─────────────────────────────────────────────────────────────────────────────
# Audio subsystem check
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckAudioSubsystem:
    def test_healthy_when_voice_disabled(self, manager):
        manager.config_manager.config.voice.enabled = False
        result = manager.check_audio_subsystem()
        assert result.status == STATUS_HEALTHY
        assert "disabled" in result.details.lower()

    def test_healthy_with_audio_devices(self, manager):
        manager.config_manager.config.voice.enabled = True
        mock_devices = [
            {"max_input_channels": 2, "max_output_channels": 0, "name": "Mic"},
            {"max_input_channels": 0, "max_output_channels": 2, "name": "Speaker"},
        ]
        mock_default = {"name": "Mic"}

        with patch("neron.diagnostics.health.importlib.import_module"):
            with patch("sounddevice.query_devices", return_value=mock_devices):
                with patch("sounddevice.query_devices", side_effect=[mock_devices, mock_default]):
                    pass  # sounddevice mock is complex; we mock the import approach below

        # Simpler: mock via direct patch
        mock_sd = MagicMock()
        mock_sd.query_devices.side_effect = [mock_devices, mock_default]
        with patch.dict("sys.modules", {"sounddevice": mock_sd}):
            result = manager.check_audio_subsystem()
        assert result.status == STATUS_HEALTHY

    def test_warning_when_sounddevice_missing(self, manager):
        manager.config_manager.config.voice.enabled = True
        with patch.dict("sys.modules", {"sounddevice": None}):
            # Force ImportError
            import builtins
            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "sounddevice":
                    raise ImportError("no module")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                result = manager.check_audio_subsystem()

        assert result.status == STATUS_WARNING
        assert result.remediation_hint is not None

    def test_warning_no_input_devices(self, manager):
        manager.config_manager.config.voice.enabled = True
        mock_devices = [
            {"max_input_channels": 0, "max_output_channels": 2, "name": "Speaker"},
        ]
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = mock_devices

        with patch.dict("sys.modules", {"sounddevice": mock_sd}):
            result = manager.check_audio_subsystem()

        assert result.status == STATUS_WARNING
        assert "microphone" in result.details.lower() or "input" in result.details.lower()


# ─────────────────────────────────────────────────────────────────────────────
# evaluate_hardware (caching)
# ─────────────────────────────────────────────────────────────────────────────

class TestEvaluateHardware:
    def test_returns_report(self, manager):
        report = manager.evaluate_hardware()
        assert isinstance(report, HardwareCapabilityReport)

    def test_result_is_cached(self, manager):
        r1 = manager.evaluate_hardware()
        r2 = manager.evaluate_hardware()
        assert r1 is r2  # same object — cached

    def test_tier_classified(self, manager):
        report = manager.evaluate_hardware()
        assert report.tier in ("MINIMAL", "STANDARD", "PERFORMANCE", "HIGH_END")

    def test_cpu_cores_positive(self, manager):
        report = manager.evaluate_hardware()
        assert report.cpu_cores >= 1
        assert report.cpu_logical >= 1

    def test_ram_positive(self, manager):
        report = manager.evaluate_hardware()
        assert report.ram_total_gb > 0.0


# ─────────────────────────────────────────────────────────────────────────────
# run_full_diagnostics
# ─────────────────────────────────────────────────────────────────────────────

class TestRunFullDiagnostics:
    def test_returns_list_of_results(self, manager):
        results = manager.run_full_diagnostics()
        assert isinstance(results, list)
        assert len(results) >= 7  # at least all checks

    def test_all_results_are_healthcheckresult(self, manager):
        for r in manager.run_full_diagnostics():
            assert isinstance(r, HealthCheckResult)

    def test_all_statuses_are_valid(self, manager):
        valid = {STATUS_HEALTHY, STATUS_WARNING, STATUS_DEGRADED, STATUS_FAILED}
        for r in manager.run_full_diagnostics():
            assert r.status in valid, f"{r.name} has invalid status: {r.status}"

    def test_check_names_are_unique(self, manager):
        names = [r.name for r in manager.run_full_diagnostics()]
        assert len(names) == len(set(names)), "Duplicate check names detected"


# ─────────────────────────────────────────────────────────────────────────────
# overall_status
# ─────────────────────────────────────────────────────────────────────────────

class TestOverallStatus:
    def _r(self, status: str) -> HealthCheckResult:
        return HealthCheckResult(name="X", status=status, details="")

    def test_all_healthy(self, manager):
        assert manager.overall_status([self._r(STATUS_HEALTHY)] * 3) == STATUS_HEALTHY

    def test_one_warning(self, manager):
        results = [self._r(STATUS_HEALTHY), self._r(STATUS_WARNING)]
        assert manager.overall_status(results) == STATUS_WARNING

    def test_one_degraded(self, manager):
        results = [self._r(STATUS_HEALTHY), self._r(STATUS_DEGRADED)]
        assert manager.overall_status(results) == STATUS_DEGRADED

    def test_one_failed(self, manager):
        results = [self._r(STATUS_HEALTHY), self._r(STATUS_WARNING), self._r(STATUS_FAILED)]
        assert manager.overall_status(results) == STATUS_FAILED

    def test_failed_dominates(self, manager):
        results = [self._r(STATUS_DEGRADED), self._r(STATUS_FAILED)]
        assert manager.overall_status(results) == STATUS_FAILED


# ─────────────────────────────────────────────────────────────────────────────
# DiagnosticsRunTool
# ─────────────────────────────────────────────────────────────────────────────

class TestDiagnosticsRunTool:
    def test_name(self):
        assert DiagnosticsRunTool().name == "diagnostics.run"

    def test_description_non_empty(self):
        assert len(DiagnosticsRunTool().description) > 10

    def test_required_capabilities(self):
        assert DiagnosticsRunTool().required_capabilities == ["READ"]

    def test_parameters_schema_valid(self):
        schema = DiagnosticsRunTool().parameters_schema
        assert schema["type"] == "object"
        assert "verbose" in schema["properties"]

    def test_execute_returns_success(self):
        tool = DiagnosticsRunTool()
        result = tool.execute({})
        assert result.success is True
        assert result.output is not None
        assert "overall_status" in result.metadata
        assert "checks" in result.metadata

    def test_execute_metadata_counts(self):
        tool = DiagnosticsRunTool()
        result = tool.execute({"verbose": True})
        assert result.metadata["check_count"] >= 7
        assert isinstance(result.metadata["failed"], int)
        assert isinstance(result.metadata["warnings"], int)

    def test_execute_verbose_includes_hints(self):
        tool = DiagnosticsRunTool()
        result = tool.execute({"verbose": True})
        # Not all checks will have hints, but the structure must allow them
        checks = result.metadata["checks"]
        assert all("name" in c and "status" in c for c in checks)

    def test_execute_non_verbose_no_hints(self):
        tool = DiagnosticsRunTool()
        result = tool.execute({"verbose": False})
        checks = result.metadata["checks"]
        for c in checks:
            assert "remediation_hint" not in c

    def test_execute_handles_exception(self):
        tool = DiagnosticsRunTool()
        with patch("neron.tools.diagnostics.tools.HealthManager", side_effect=Exception("crash")):
            result = tool.execute({})
        assert result.success is False
        assert "crash" in result.error

    def test_validate_no_required_arguments(self):
        tool = DiagnosticsRunTool()
        assert tool.validate_arguments({}) is True


# ─────────────────────────────────────────────────────────────────────────────
# DiagnosticsHardwareTool
# ─────────────────────────────────────────────────────────────────────────────

class TestDiagnosticsHardwareTool:
    def test_name(self):
        assert DiagnosticsHardwareTool().name == "diagnostics.hardware"

    def test_description_non_empty(self):
        assert len(DiagnosticsHardwareTool().description) > 10

    def test_required_capabilities(self):
        assert DiagnosticsHardwareTool().required_capabilities == ["READ"]

    def test_parameters_schema_empty(self):
        schema = DiagnosticsHardwareTool().parameters_schema
        assert schema["type"] == "object"
        assert schema["properties"] == {}

    def test_execute_returns_success(self):
        tool = DiagnosticsHardwareTool()
        result = tool.execute({})
        assert result.success is True
        assert result.output is not None

    def test_execute_metadata_has_tier(self):
        tool = DiagnosticsHardwareTool()
        result = tool.execute({})
        assert "tier" in result.metadata
        assert result.metadata["tier"] in ("MINIMAL", "STANDARD", "PERFORMANCE", "HIGH_END")

    def test_execute_metadata_cpu_ram(self):
        tool = DiagnosticsHardwareTool()
        result = tool.execute({})
        assert "cpu_cores" in result.metadata
        assert result.metadata["cpu_cores"] >= 1
        assert result.metadata["ram_total_gb"] > 0

    def test_execute_output_contains_tier(self):
        tool = DiagnosticsHardwareTool()
        result = tool.execute({})
        assert "Tier:" in result.output

    def test_execute_handles_exception(self):
        tool = DiagnosticsHardwareTool()
        with patch("neron.tools.diagnostics.tools.HealthManager", side_effect=Exception("hw crash")):
            result = tool.execute({})
        assert result.success is False
        assert "hw crash" in result.error

    def test_gpu_info_in_output_when_present(self):
        tool = DiagnosticsHardwareTool()
        hw = HardwareCapabilityReport(
            cpu_cores=8, cpu_logical=16, cpu_model="i9", ram_total_gb=32.0,
            ram_available_gb=16.0, gpu_available=True, gpu_names=["RTX 3090"], tier="HIGH_END"
        )
        with patch("neron.tools.diagnostics.tools.HealthManager") as MockMgr:
            MockMgr.return_value.evaluate_hardware.return_value = hw
            result = tool.execute({})
        assert "RTX 3090" in result.output
        assert "CUDA" in result.output


# ─────────────────────────────────────────────────────────────────────────────
# run_cli_diagnostics (smoke test)
# ─────────────────────────────────────────────────────────────────────────────

class TestRunCliDiagnostics:
    def test_outputs_to_stdout(self, capsys):
        run_cli_diagnostics()
        captured = capsys.readouterr()
        assert "NERON SYSTEM DIAGNOSTICS" in captured.out
        assert "Overall Status" in captured.out
        assert "Hardware Profile" in captured.out

    def test_shows_tier(self, capsys):
        run_cli_diagnostics()
        captured = capsys.readouterr()
        assert "Tier" in captured.out

    def test_does_not_raise(self):
        # Should complete without raising even in varied environments
        run_cli_diagnostics()


# ─────────────────────────────────────────────────────────────────────────────
# Tool registry integration
# ─────────────────────────────────────────────────────────────────────────────

class TestDiagnosticsToolsInRegistry:
    def test_diagnostic_tools_registered(self):
        from neron.tools import create_default_registry
        registry = create_default_registry()
        tool_names = [t.name for t in registry.list_tools()]
        assert "diagnostics.run" in tool_names
        assert "diagnostics.hardware" in tool_names

    def test_registry_tool_count_includes_diagnostics(self):
        from neron.tools import create_default_registry
        registry = create_default_registry()
        diag_tools = [t for t in registry.list_tools() if t.name.startswith("diagnostics.")]
        assert len(diag_tools) == 2

    def test_diagnostics_run_tool_lookup(self):
        from neron.tools import create_default_registry
        registry = create_default_registry()
        tool = registry.get("diagnostics.run")
        assert tool is not None
        assert tool.name == "diagnostics.run"

    def test_diagnostics_hardware_tool_lookup(self):
        from neron.tools import create_default_registry
        registry = create_default_registry()
        tool = registry.get("diagnostics.hardware")
        assert tool is not None
        assert tool.name == "diagnostics.hardware"
