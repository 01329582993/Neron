"""Unit tests for PermissionManager, Security Policies, and Emergency Stop."""

import pytest
from neron.security.emergency_stop import EmergencyStopCoordinator, EmergencyStopTriggered
from neron.security.permissions import Capability, PermissionDecision, PermissionRequest, SecurityMode
from neron.security.policy import PermissionDeniedError, PermissionManager


def test_safe_mode_prompts_on_modification():
    manager = PermissionManager(mode=SecurityMode.SAFE, prompt_handler=lambda req: False)

    # Read-only operation should be auto-granted
    req_read = PermissionRequest(tool_name="filesystem.read", required_capabilities=[Capability.FILESYSTEM_READ])
    decision = manager.evaluate(req_read)
    assert decision == PermissionDecision.GRANTED

    # Write operation should prompt, and since handler returns False, raises PermissionDeniedError
    req_write = PermissionRequest(tool_name="filesystem.write", required_capabilities=[Capability.FILESYSTEM_WRITE])
    with pytest.raises(PermissionDeniedError):
        manager.evaluate(req_write)


def test_standard_mode_allows_standard_writes():
    # In STANDARD mode, non-destructive writes are granted without prompt
    manager = PermissionManager(mode=SecurityMode.STANDARD)
    req_write = PermissionRequest(tool_name="filesystem.write", required_capabilities=[Capability.FILESYSTEM_WRITE])
    decision = manager.evaluate(req_write)
    assert decision == PermissionDecision.GRANTED

    # High-risk deletion requires confirmation
    manager.set_prompt_handler(lambda req: True)
    req_delete = PermissionRequest(tool_name="filesystem.delete", required_capabilities=[Capability.FILESYSTEM_DELETE])
    decision = manager.evaluate(req_delete)
    assert decision == PermissionDecision.PROMPTED_APPROVED


def test_protected_system_path_guardrail():
    manager = PermissionManager(mode=SecurityMode.POWER_USER)
    req_bad = PermissionRequest(
        tool_name="filesystem.write",
        required_capabilities=[Capability.FILESYSTEM_WRITE],
        arguments={"path": "C:\\Windows\\System32\\malicious.dll"}
    )
    with pytest.raises(PermissionDeniedError) as exc_info:
        manager.evaluate(req_bad)
    assert "protected system directory" in str(exc_info.value)


def test_emergency_stop_lifecycle():
    stop_coord = EmergencyStopCoordinator()
    assert not stop_coord.is_stopped()

    cleanup_called = []
    stop_coord.register_cleanup_hook(lambda: cleanup_called.append(True))

    stop_coord.trigger(reason="Test Stop")
    assert stop_coord.is_stopped()
    assert len(cleanup_called) == 1

    with pytest.raises(EmergencyStopTriggered):
        stop_coord.assert_not_stopped()

    stop_coord.reset()
    assert not stop_coord.is_stopped()
    stop_coord.assert_not_stopped()  # should not raise now
