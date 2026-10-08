# 🛡️ NERON Security & Permission Specification

## 1. Security Philosophy

Because **Neron** is an agent designed with full computer operation capabilities, security cannot be an afterthought or a hidden mechanism. Neron adheres to five fundamental security tenets:

1. **Explicit Permission Governance**: Every tool action declares the precise capabilities it requires. No tool possesses arbitrary unmonitored system access.
2. **User Agency and Transparency**: The user retains complete authority over what Neron is permitted to do. No background actions occur without conforming to the user-selected security profile.
3. **No OS Security Bypasses**: Neron never bypasses User Account Control (UAC) on Windows, `sudo`/Polkit on Linux, or root sandboxes.
4. **Hard Emergency Interruption**: A physical and software emergency stop can immediately cancel any ongoing automation routine.
5. **Zero-Secret Logging**: Credentials, environment secrets, and sensitive tokens are automatically scrubbed from developer logs and audit databases.

---

## 2. Capability Permission Matrix

Every tool registered in Neron must declare one or more permissions from this standardized capability matrix:

| Capability Identifier | Description | Risk Level |
| :--- | :--- | :---: |
| `filesystem.read` | Read files, scan directories, inspect file metadata | Low |
| `filesystem.write` | Create or update non-system files in user workspace | Medium |
| `filesystem.delete` | Delete or move files/directories to trash | High |
| `terminal.execute` | Execute shell/terminal commands and scripts | High |
| `computer.screen` | Capture desktop screenshots and inspect visible UI | Medium |
| `computer.mouse` | Move cursor, click buttons, drag and scroll | Medium |
| `computer.keyboard` | Type text, press keys, trigger hotkeys | High |
| `application.control` | Launch, focus, resize, or terminate applications | Medium |
| `system.inspect` | Read CPU, RAM, disk, battery, and process telemetry | Low |
| `system.admin` | Change system settings, network adapters, or service states | Critical |
| `network.access` | Make outbound HTTP/network requests to external APIs | Medium |
| `self.modify` | Propose, test, or stage updates to Neron source code | Critical |
| `plugin.install` | Load, install, or activate third-party plugins | Critical |

---

## 3. Operational Security Profiles

Users configure their active security posture via `config/neron.yaml` or the UI console.

### 🛡️ `SAFE` Mode (Recommended for evaluation)
- **Allowed automatically**: Strictly read-only capabilities (`filesystem.read`, `system.inspect`, `computer.screen`).
- **Confirmation required**: Every modification, application launch, keypress, terminal command, or file write requires explicit user approval.

### ⚖️ `STANDARD` Mode (Default for daily usage)
- **Allowed automatically**: Non-destructive user-level actions (reading files, taking screenshots, launching applications, standard non-critical file writes).
- **Confirmation required**:
  - `terminal.execute`
  - `filesystem.delete`
  - `system.admin`
  - `self.modify`
  - `plugin.install`

### ⚡ `POWER_USER` Mode (For automated workflows)
- **Allowed automatically**: All standard file operations, mouse/keyboard automation, and safe terminal executions within the user space.
- **Confirmation required**:
  - `system.admin` (Elevated privileges / UAC / sudo)
  - Destructive batch operations (`filesystem.delete` on non-empty directories)
  - `self.modify` (Source code changes)

### 🎛️ `CUSTOM` Mode
- The user defines explicit white-lists, black-lists, and path boundaries in `config/neron.yaml`.

---

## 4. Protected System Paths & Guardrails

Even in `POWER_USER` mode, Neron enforces hardcoded path protections preventing automated destructive actions against critical operating system directories:

- **Windows**:
  - `C:\Windows\`
  - `C:\Program Files\` (except registered application binaries)
  - `C:\Program Files (x86)\`
- **Linux**:
  - `/etc/`
  - `/boot/`
  - `/sys/`
  - `/usr/` (outside user's `$HOME`)
  - `/bin/`, `/sbin/`

Attempts to write, overwrite, or delete paths inside protected system roots are immediately blocked with an `AccessDeniedError` unless explicitly confirmed through root/administrative elevation with user prompt.

---

## 5. Emergency Stop Protocol (`CTRL + ALT + N`)

Neron incorporates a dedicated background interrupt listener:
1. When the user presses `CTRL + ALT + N` (or says *"Neron, STOP"*), an immediate `EmergencyStopEvent` is published to the `EventBus`.
2. The `ExecutionEngine` instantly halts active plan dispatch.
3. Active child subprocesses launched by `terminal.execute` are sent `SIGTERM` / `SIGKILL` signals.
4. Mouse and keyboard control hooks are immediately unhooked and released.
5. The state machine transitions to `CANCELLED`, and an audit event is persisted.

---

## 6. Audit Trail & Log Sanitization

All actions dispatched by the agent are recorded in an SQLite audit database (`data/audit.db`):
- `timestamp` (ISO 8601 UTC)
- `task_id` and `step_id`
- `tool_name`
- `requested_capabilities`
- `permission_decision` (`GRANTED`, `PROMPTED_APPROVED`, `DENIED`)
- `execution_status` (`SUCCESS`, `FAILED`, `ABORTED`)
- `duration_ms`

**Sanitization**: Pattern matchers scrub API keys, authorization bearer tokens, SSH keys, passwords, and sensitive environment variables from both console logs and the audit database.

---

## 7. Reporting a Vulnerability

If you discover a potential security vulnerability in Neron:
1. Do not open a public issue on GitHub.
2. Contact the development team or maintainers privately.
3. Provide steps to reproduce the vulnerability, including your operating system, active security profile, and proof-of-concept commands.
