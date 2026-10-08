# 📜 NERON Changelog

All notable changes to the Neron platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0-alpha] - 2026-10-08

### Added
- **Architectural Specifications & Documentation**:
  - `README.md`: Project mission, core philosophies, quick start, and directory architecture.
  - `ARCHITECTURE.md`: Subsystem boundaries, sequence diagrams, verification contract, and degradation models.
  - `ROADMAP.md`: Staged 15-milestone roadmap detailing current and future development phases.
  - `SECURITY.md`: Capability permission matrix, operational security modes (`SAFE`, `STANDARD`, `POWER_USER`, `CUSTOM`), protected path rules, and emergency stop protocol.
  - `CONTRIBUTING.md`: Coding standards, development rules, testing guidelines, and PR checklist.
  - `PLUGIN_DEVELOPMENT.md`: Third-party extension guide, manifest specification (`plugin.yaml`), and sandbox isolation.
  - `DEVELOPMENT_AGENT.md`: Sandboxed self-extension loop (`Understand` → `Plan` → `Modify` → `Test` → `Deploy`) and safety controls.
  - `INSTALLATION.md`: Cross-platform setup, hardware requirements, and local Ollama setup.
  - `TROUBLESHOOTING.md`: Built-in diagnostic commands, permission issues, audio fixes, and audit history inspection.
  - `CHANGELOG.md`: Project history and release tracking.

- **Developer Automation**:
  - Cross-platform bootstrap scripts: `scripts/setup.ps1` and `scripts/setup.sh`.
  - Automated test runners: `scripts/test.ps1` and `scripts/test.sh`.
  - Development console launchers: `scripts/dev.ps1` and `scripts/dev.sh`.
  - `pyproject.toml` package manifest with development dependencies and entrypoints.

- **Core Infrastructure (Stage 1 & 2)**:
  - Event Bus (`neron.core.events.bus`): Thread-safe, asynchronous decoupled pub/sub event dispatcher.
  - Security Engine (`neron.security`): `PermissionManager`, capability enforcement, and `EmergencyStop` coordinator (`CTRL+ALT+N`).
  - OS Abstraction Layer (`neron.os`): Abstract `OSController`, `WindowsController`, and `LinuxController` for cross-platform system, window, and process control.
  - Tool Architecture (`neron.tools`): `BaseTool`, `ToolResult`, and `ToolRegistry` with permission checks and validation hooks.
  - Diagnostics (`neron.diagnostics`): `HealthManager` for runtime environment audits.
