# 📜 NERON Changelog

All notable changes to the Neron platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.0-alpha] - 2026-10-09

### Added
- **Stage 6 — DAG Task Planning & Execution Engine**:
  - Enhanced `PlanStep` and `TaskPlan` models with DAG `depends_on` edges, `is_optional`, `rollback_step`, `VerificationResult`, `FailureAnalysis`, `SKIPPED` state, `warnings`, and `rollback_log`.
  - `neron/core/executor/failure_analyzer.py`: Typed failure classifier with 7 failure modes (`PERMISSION_DENIED`, `TIMEOUT`, `TOOL_NOT_FOUND`, `VERIFICATION_FAILED`, `DEPENDENCY_FAILED`, `EMERGENCY_STOP`, `TOOL_RUNTIME_ERROR`), each producing actionable recovery suggestions.
  - `neron/core/executor/verifier.py`: Post-step verification engine with per-tool strategies (filesystem re-read, terminal exit code inspection, system tool result trust).
  - `neron/core/executor/dag_executor.py`: Full DAG executor using Kahn's topological sort with cycle detection, dependency resolution, exponential retry back-off (0.5→1.5→3.0s), optional step handling, downstream failure propagation, and rollback execution.
  - `neron/core/planner/dag_planner.py`: DAGPlanner generating multi-step plans with explicit dependency chains for composite workflows (prepare dev env, write-then-read, check-then-open, search-then-open).
  - `tests/test_dag_engine.py`: 26 new tests covering FailureAnalyzer, StepVerifier, DAGPlanner, and DAGExecutor (topology, rollback, optional steps, cycle detection, emergency stop, downstream propagation).

- **Stage 7 — Desktop Operating Console & UI**:
  - `neron/ui/console.py`: `NeronConsole` — Rich-powered terminal UI with live system telemetry bar (CPU/RAM bars with color coding), task history table (up to 8 recent plans), active plan step breakdown with state icons, retry count, duration, inline error messages and recovery hints, and a scrollable response panel.
  - `neron/__main__.py`: Integrated `DAGPlanner` + `DAGExecutor` + `NeronConsole` into the interactive REPL. All natural language goals now go through the DAG pipeline. Rich plan summary (with rollback log and warnings) is displayed after every execution.

### Changed
- `neron/core/executor/__init__.py`: Now exports `DAGExecutor`, `DAGExecutionError`, `analyze_failure`, and `verify_step`.
- `neron/core/planner/__init__.py`: Now exports `DAGPlanner`.
- `ROADMAP.md`: Stages 6 and 7 marked ✅ Complete.

### Test Suite
- **64/64 tests passing** (38 previous + 26 new Stage 6 tests, zero regressions).

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
