"""Security policy engine and permission evaluation manager for Neron."""

import os
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set
from neron.core.events.bus import EventBus, get_default_bus
from neron.core.events.event import EVENT_SECURITY_DECISION, EVENT_SECURITY_PROMPT, Event
from neron.security.permissions import Capability, PermissionDecision, PermissionRequest, SecurityMode
from neron.utils.audit import AuditLedger
from neron.utils.logger import get_logger

logger = get_logger("security.policy")

PromptHandler = Callable[[PermissionRequest], bool]


class PermissionDeniedError(Exception):
    """Raised when an operation is rejected by the permission engine."""
    def __init__(self, message: str, request: PermissionRequest, decision: PermissionDecision):
        super().__init__(message)
        self.request = request
        self.decision = decision


class PermissionManager:
    """Evaluates and enforces capability permissions against active security policies."""

    # Paths that are strictly protected against automated mutation or deletion
    PROTECTED_SYSTEM_PATHS = [
        "c:\\windows",
        "c:\\program files",
        "c:\\program files (x86)",
        "/etc",
        "/boot",
        "/sys",
        "/usr/bin",
        "/usr/sbin",
        "/bin",
        "/sbin",
    ]

    def __init__(
        self,
        mode: SecurityMode = SecurityMode.STANDARD,
        prompt_handler: Optional[PromptHandler] = None,
        audit_ledger: Optional[AuditLedger] = None,
        event_bus: Optional[EventBus] = None,
        custom_policies: Optional[Dict[str, bool]] = None,
    ):
        self.mode = mode
        self.prompt_handler = prompt_handler or self._default_cli_prompt
        self.audit_ledger = audit_ledger or AuditLedger()
        self.event_bus = event_bus or get_default_bus()
        self.custom_policies = custom_policies or {}

    def set_mode(self, mode: SecurityMode) -> None:
        """Update active security mode."""
        logger.info(f"Security mode switched to: {mode.value}")
        self.mode = mode

    def set_prompt_handler(self, handler: PromptHandler) -> None:
        """Set custom user confirmation prompt handler (for UI, TTY, or tests)."""
        self.prompt_handler = handler

    def check_protected_path(self, target_path_str: str) -> bool:
        """Return True if path is a protected operating system directory."""
        if not target_path_str:
            return False
        try:
            resolved = str(Path(target_path_str).resolve()).lower()
            for protected in self.PROTECTED_SYSTEM_PATHS:
                if resolved.startswith(protected.lower()):
                    return True
        except Exception:
            pass
        return False

    def evaluate(self, request: PermissionRequest) -> PermissionDecision:
        """Evaluate a permission request against active policies."""
        # 1. Protected path guardrail check
        target_path = request.arguments.get("path") or request.arguments.get("directory") or request.arguments.get("target")
        if target_path and isinstance(target_path, str):
            for cap in request.required_capabilities:
                if cap in {Capability.FILESYSTEM_WRITE, Capability.FILESYSTEM_DELETE}:
                    if self.check_protected_path(target_path):
                        logger.warning(f"Blocked destructive action on protected path: {target_path}")
                        self._record(request, PermissionDecision.DENIED, success=False)
                        raise PermissionDeniedError(
                            f"Access Denied: Path '{target_path}' is a protected system directory.",
                            request,
                            PermissionDecision.DENIED
                        )

        # 2. Policy evaluation based on mode
        needs_prompt = self._requires_confirmation(request)

        if not needs_prompt:
            decision = PermissionDecision.GRANTED
            self._record(request, decision, success=True)
            return decision

        # 3. Prompt user for confirmation
        self.event_bus.publish(Event(
            event_type=EVENT_SECURITY_PROMPT,
            payload={
                "tool_name": request.tool_name,
                "capabilities": request.required_capabilities,
                "arguments": request.arguments,
                "reason": request.reason,
            }
        ))

        approved = self.prompt_handler(request)
        decision = PermissionDecision.PROMPTED_APPROVED if approved else PermissionDecision.PROMPTED_DENIED

        self._record(request, decision, success=approved)

        if not approved:
            raise PermissionDeniedError(
                f"Action rejected by user for tool '{request.tool_name}' (Capabilities: {request.required_capabilities})",
                request,
                decision
            )

        return decision

    def _requires_confirmation(self, request: PermissionRequest) -> bool:
        """Determine if a capability set requires explicit user confirmation."""
        caps = set(request.required_capabilities)

        if self.mode == SecurityMode.SAFE:
            # SAFE mode requires confirmation for ANY state-modifying capability
            read_only_caps = {Capability.FILESYSTEM_READ, Capability.SYSTEM_INSPECT, Capability.COMPUTER_SCREEN}
            return not caps.issubset(read_only_caps)

        elif self.mode == SecurityMode.STANDARD:
            # High risk or critical capabilities require confirmation
            always_prompt = {
                Capability.TERMINAL_EXECUTE,
                Capability.FILESYSTEM_DELETE,
                Capability.SYSTEM_ADMIN,
                Capability.SELF_MODIFY,
                Capability.PLUGIN_INSTALL,
            }
            return bool(caps & always_prompt)

        elif self.mode == SecurityMode.POWER_USER:
            # Only critical actions require confirmation
            critical_caps = {
                Capability.SYSTEM_ADMIN,
                Capability.SELF_MODIFY,
            }
            return bool(caps & critical_caps)

        elif self.mode == SecurityMode.CUSTOM:
            for cap in caps:
                # If custom policy explicitly requires prompt (False means not pre-approved)
                if not self.custom_policies.get(cap, False):
                    return True
            return False

        return True

    def _default_cli_prompt(self, request: PermissionRequest) -> bool:
        """Default interactive confirmation prompt for CLI."""
        print("\n" + "=" * 55)
        print(f"⚠️  NERON SECURITY PERMISSION REQUEST")
        print(f"   Tool:         {request.tool_name}")
        print(f"   Capabilities: {', '.join(request.required_capabilities)}")
        if request.arguments:
            print(f"   Arguments:    {request.arguments}")
        if request.reason:
            print(f"   Reason:       {request.reason}")
        print("=" * 55)
        try:
            choice = input("Authorize this action? [y/N]: ").strip().lower()
            return choice in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    def _record(self, request: PermissionRequest, decision: PermissionDecision, success: bool) -> None:
        """Log decision to audit ledger and publish event."""
        self.audit_ledger.record_event(
            tool_name=request.tool_name,
            capabilities=request.required_capabilities,
            decision=decision.value,
            success=success,
            task_id=request.task_id,
            step_id=request.step_id,
            arguments=request.arguments,
            result_summary=f"Permission {decision.value}",
        )
        self.event_bus.publish(Event(
            event_type=EVENT_SECURITY_DECISION,
            payload={
                "tool_name": request.tool_name,
                "capabilities": request.required_capabilities,
                "decision": decision.value,
                "task_id": request.task_id,
            }
        ))
