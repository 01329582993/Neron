"""Unit tests for OS abstraction controller."""

import pytest
from neron.os.base import OSController, get_os_controller


def test_os_controller_factory():
    ctrl = get_os_controller()
    assert isinstance(ctrl, OSController)
    platform_name = ctrl.get_platform_name()
    assert platform_name in ("windows", "linux", "macos")


def test_system_telemetry():
    ctrl = get_os_controller()
    t = ctrl.get_telemetry()
    assert t.cpu_count > 0
    assert t.memory_total_gb > 0
    assert 0 <= t.memory_percent <= 100
    assert t.disk_total_gb > 0


def test_process_listing():
    ctrl = get_os_controller()
    procs = ctrl.list_processes()
    assert len(procs) > 0
    # Current python process should be listed
    found_py = [p for p in procs if "python" in p.name.lower()]
    assert len(found_py) > 0


def test_terminal_command_execution():
    ctrl = get_os_controller()
    cmd = "echo 'NERON_TEST'"
    res = ctrl.execute_terminal_command(cmd, timeout=5)
    assert res["exit_code"] == 0
    assert "NERON_TEST" in res["stdout"]
    assert res["duration_ms"] >= 0


def test_terminal_command_timeout():
    ctrl = get_os_controller()
    # Execute command that sleeps longer than timeout
    if ctrl.get_platform_name() == "windows":
        cmd = "Start-Sleep -Seconds 5"
    else:
        cmd = "sleep 5"

    res = ctrl.execute_terminal_command(cmd, timeout=1)
    assert res["timed_out"] is True
    assert res["exit_code"] == -1
