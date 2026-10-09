# 📜 NERON Changelog

All notable changes to the Neron platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-rc1] - 2026-10-09

### Added
- **Stage 15 — Cross-Platform Packaging & Distribution Pipelines**:
  - `neron/packaging/config.py`: `PackagingConfig` governing cross-platform distribution builds across Windows, Linux, and standalone offline packages.
  - `neron/packaging/spec.py`: `PyInstallerSpecGenerator` producing complete, reproducible PyInstaller `.spec` files bundling all core runtime dependencies, hidden imports, and assets.
  - `neron/packaging/windows.py`:
    - `WindowsPackager`: Builds Windows standalone executable command lines and generates customized InnoSetup `.iss` installers with Start Menu shortcuts, desktop icons, and uninstallation routines.
  - `neron/packaging/linux.py`:
    - `LinuxPackager`: Generates Freedesktop AppImage directory trees (`AppDir/AppRun`, `neron.desktop`, icon) and Debian package trees (`DEBIAN/control`, `postinst`, `prerm`).
  - `neron/packaging/offline.py`:
    - `OfflineBundleGenerator`: Produces self-contained offline installer distributions with preconfigured local Ollama/GGUF fallback routing, bootstrap scripts (`install_offline.bat` and `install_offline.sh`), and a SHA256 integrity inventory (`bundle_manifest.json`).
  - `neron/packaging/builder.py`: `PackageBuilder` unifying multi-platform packaging commands.
  - Distribution build automation scripts in `scripts/`:
    - `scripts/build_windows.ps1`: Automated PowerShell builder for Windows executables and InnoSetup installers.
    - `scripts/build_linux.sh`: Automated bash builder for Linux AppImages and Debian packages.
    - `scripts/build_offline.py`: Python CLI generator for zero-config offline bundles.
  - `tests/test_packaging.py`: 14 comprehensive unit and integration tests covering spec generation, InnoSetup directives, Linux packaging, SHA256 offline manifests, and multi-platform builders.

### Test Suite
- **293/293 tests passing** (279 previous + 14 new Stage 15 tests, zero regressions).
- **All 16 development roadmap milestones (Stages 0–15) 100% COMPLETE!**

---

## [0.10.0-alpha] - 2026-10-09

### Added
- **Stage 14 — Sandboxed Self-Update Pipeline & Automated Rollback**:
  - `neron/developer/staging.py`:
    - `StagingWorkspace`: Isolated staging sandbox creator (`.neron/staging/workspace/`) with stage management, unified diff generation against production, and clean reset.
  - `neron/developer/backup.py`:
    - `BackupManager`: Timestamped backup snapshot creator in `.neron/backups/<backup_id>/` with metadata serialization, file inventory, newest-first listing, and one-click restoration.
  - `neron/developer/validator.py`:
    - `ValidationGate`: Pre-deployment verification gate checking Python AST syntax errors, security violations / protected system paths, and executing automated test suites via `TestRunner`.
  - `neron/developer/updater.py`:
    - `SelfUpdatePipeline`: Full Development Loop orchestrator coordinating staging, pre-deployment validation, atomic copy to production tree, post-deployment runtime health checks with `HealthManager`, and automated instant rollback on failure.
  - `neron/tools/developer/`:
    - `dev.stage_patch`: Stages proposed code changes into the isolated `.neron/staging/` workspace.
    - `dev.deploy_staged`: Atomically deploys staged modifications after pre-deployment validation and creates an instant backup checkpoint.
    - `dev.rollback`: Instantly restores the production workspace from a previous backup snapshot.
  - Registered all self-update tools in default `ToolRegistry` and wired natural language intents in `DAGPlanner`.
  - `tests/test_updater.py`: 25 comprehensive unit and integration tests covering staging, snapshot backups, pre-deployment gate, atomic deployment, health-check triggered auto-rollback, and DAG planning.

### Test Suite
- **279/279 tests passing** (254 previous + 25 new Stage 14 tests, zero regressions).

---

## [0.9.0-alpha] - 2026-10-09

### Added
- **Stage 13 — Developer Agent & Self-Improvement Subsystem**:
  - `neron/developer/introspector.py`:
    - `CodeIntrospector`: AST-powered Python source analyzer extracting class definitions, method signatures, return types, line spans, docstrings, imports, and top-level constants.
    - Syntax validator verifying code strings without execution via `compile`/`ast.parse` and returning line numbers and error diagnostics.
    - Symbol locator scanning repository files to find matching functions and classes across modules.
  - `neron/developer/test_runner.py`:
    - `TestRunner`: Automated subprocess-based pytest execution engine with timeout isolation, coverage reporting, and structured result parsing (`TestResult`).
    - Robust pytest summary parser extracting pass/fail/skip/error counts, execution duration, and failure traces.
  - `neron/developer/patcher.py`:
    - `PatchGenerator`: Generates unified diffs (`difflib.unified_diff`) and applies patch hunks to target files.
    - `PatchValidator`: Validates proposed code patches against protected system paths, dangerous patterns (root deletion, unbounded directory recursion), and Python AST syntax errors.
  - `neron/developer/scaffolder.py`:
    - `PluginScaffolder`: Complete plugin scaffolding generator (`neron plugin create <name>`) producing fully compliant plugin directories with `plugin.yaml` manifest, `PluginBase` lifecycle subclass, `BaseTool` implementation, unit tests, and README.
  - `neron/developer/agent.py`:
    - `DeveloperAgent`: Master coordinator providing unified interfaces for introspection, testing, patch creation, scaffolding, and error diagnosis with remediation hints.
  - `neron/tools/developer/`:
    - `dev.inspect_source`: Inspects modules or files for AST structure and docstrings.
    - `dev.run_tests`: Executes pytest suites and returns structured execution metrics.
    - `dev.validate_code`: Validates Python syntax and structure without execution.
    - `dev.create_plugin`: Scaffolds verified plugin extensions into `plugins/`.
  - Registered all developer tools in default `ToolRegistry` and added intent patterns in `DAGPlanner`.
  - CLI commands in `neron/__main__.py`:
    - `neron plugin create <name> [--desc DESC] [--tool TOOL]`
    - `neron --test [TARGET]`
    - `neron --inspect <MODULE_OR_FILE>`
  - `tests/test_developer.py`: 40 comprehensive unit and integration tests covering AST parsing, test runner parsing, patch generation, plugin runtime verification, developer tools, and DAG planning.

### Test Suite
- **254/254 tests passing** (214 previous + 40 new Stage 13 tests, zero regressions).

---

## [0.8.0-alpha] - 2026-10-09

### Added
- **Stage 12 — Self-Diagnostics & Health System**:
  - `neron/diagnostics/health.py`:
    - `HealthManager`: Comprehensive runtime system auditor checking Python environment (>=3.11), disk storage (>5GB threshold), local Ollama LLM endpoint availability, internet connectivity & round-trip latency, microphone/speaker accessibility via sounddevice/pyttsx3, and OS controller responsiveness.
    - `HardwareCapabilityReport`: Automated hardware classification detecting physical and logical CPU cores, total/available RAM, and NVIDIA/AMD/DirectX GPU acceleration via `torch.cuda` or OS telemetry. Categorizes systems into compute tiers (`HIGH_END`, `PERFORMANCE`, `STANDARD`, `MINIMAL`) and suggests optimal local LLM models (e.g. `llama3:70b`, `qwen2.5:14b`, `mistral:7b`, `phi-3:mini`).
    - `run_cli_diagnostics()`: ANSI-formatted diagnostic summary with color-coded health badges and remediation hints for the `--diagnose` CLI flag.
  - `neron/tools/diagnostics/`:
    - `diagnostics.run`: Invokes environment auditing and returns structured component status and remediation hints.
    - `diagnostics.hardware`: Returns hardware metrics, compute tier, and model recommendations.
  - Registered diagnostic tools in default `ToolRegistry` and wired natural language intents in `DAGPlanner`.
  - CLI integration in `neron/__main__.py` with `--diagnose` command flag.
  - `tests/test_diagnostics.py`: 88 comprehensive tests covering all audit routines, hardware tiers, caching, CLI output, and mock isolation.

### Test Suite
- **214/214 tests passing** (126 previous + 88 new Stage 12 tests, zero regressions).

---

## [0.7.0-alpha] - 2026-10-09

### Added
- **Stage 11 — Modular Online Integrations**:
  - `neron/network/observer.py`: `NetworkObserver` for continuous or on-demand connectivity checks with configurable TTL cache, socket pinging, and `network.status_changed` event publication.
  - `neron/network/search.py`: `SearchEngineRouter` coordinating pluggable web search providers (`DuckDuckGoProvider`, `SearXNGProvider`, `MockSearchProvider`) with automated failover.
  - `neron/network/web_reader.py`: `WebReader` extracting and cleaning web content with BeautifulSoup HTML stripping, readability heuristics, and token-efficient markdown generation.
  - `neron/tools/network/`:
    - `network.status`: Checks live internet availability and connection latency.
    - `network.search`: Queries the web with configurable search engines and limits.
    - `network.fetch_page`: Retrieves cleaned webpage content with word count constraints.
  - `tests/test_network.py`: 14 tests covering network observation, search fallback routing, web extraction, and DAG planning.

### Test Suite
- **126/126 tests passing** (112 previous + 14 new Stage 11 tests, zero regressions).

---

## [0.6.0-alpha] - 2026-10-09

### Added
- **Stage 10 — Plugin Architecture & Extensibility**:
  - `neron/plugins/base.py`: `PluginBase` abstract lifecycle class, `PluginMetadata` declaration contract, and `PluginState` lifecycle enum (`DISCOVERED`, `LOADED`, `ENABLED`, `DISABLED`, `ERROR`).
  - `neron/plugins/manifest.py`: `PluginManifestValidator` parsing and validating both `plugin.yaml` and `plugin.json` manifests, validating required fields (`id`, `name`, `version`), declared permissions, and exposed tools.
  - `neron/plugins/loader.py`: `PluginLoader` utilizing Python `importlib.util` for dynamic isolated module loading, locating `PluginBase` subclasses, and instantiation.
  - `neron/plugins/manager.py`: `PluginManager` providing directory scanning, manifest discovery, dependency validation, lifecycle coordination (`discover`, `load`, `enable`, `disable`, `reload`), and tool registry injection/ejection.
  - Example Community Plugins:
    - `plugins/neron_system_monitor/`: System health and threshold monitor exporting `sysmon.check_status` tool.
    - `plugins/neron_media_controller/`: Desktop media playback automation exporting `media.play_pause` and `media.next` tools.
  - `tests/test_plugins.py`: 12 new unit and integration tests covering manifest parsing, dynamic loading, lifecycle hooks, tool registry injection, and example plugins.

### Test Suite
- **112/112 tests passing** (100 previous + 12 new Stage 10 tests, zero regressions).

---

## [0.5.0-alpha] - 2026-10-09


### Added
- **Stage 9 — Memory Subsystem (Persistent Facts, Working Scratchpad & Procedural Recipes)**:
  - `neron/memory/sqlite_store.py`: Thread-safe `SQLiteMemoryStore` supporting structured facts (`facts` table with category, key, value, confidence), conversation turns history (`conversation_turns` table), procedural recipes (`recipes` table with usage counters), and SQLite FTS5 full-text search with LIKE fallback.
  - `neron/memory/working_memory.py`: Volatile in-memory `WorkingMemory` scratchpad managing session state, active goals, plan IDs, context variables (`set_variable`/`get_variable`), and turn history with sliding window eviction.
  - `neron/memory/recipes.py`: `RecipeManager` enabling registration and natural-language regex pattern matching for multi-step automated task templates.
  - `neron/memory/manager.py`: Unified `MemoryManager` facade coordinating fact storage, working memory, procedural recipes, and prompt context summarization for LLMs.
  - `neron/tools/memory/`: 3 new memory tools registered in `ToolRegistry`:
    - `memory.remember`: stores facts, user preferences, and system parameters
    - `memory.recall`: retrieves facts by exact key or search query
    - `memory.forget`: deletes facts from memory
  - `neron/core/planner/dag_planner.py`: Extended DAG planner to match procedural automation recipes and map natural language statements ("remember that X is Y", "recall X", "forget X") directly into memory tool plans.
  - `tests/test_memory.py`: 17 new unit and integration tests covering SQLite store, working memory, recipe manager, memory manager, memory tools, and DAG planner expansions.

### Test Suite
- **100/100 tests passing** (83 previous + 17 new Stage 9 tests, zero regressions).

---

## [0.4.0-alpha] - 2026-10-09

 
### Added
- **Stage 8 — Computer Vision & Screen Reasoning Subsystem**:
  - `neron/vision/capture.py`: `ScreenCapture` engine supporting fast multi-monitor screenshot capture via MSS with seamless Pillow `ImageGrab` fallback and mock/headless testing injection.
  - `neron/vision/analyzer.py`: `ScreenAnalyzer` utilizing OpenCV for normalized cross-correlation template matching, non-maximum suppression (NMS) duplicate elimination, low-variance/flat image handling via `TM_SQDIFF`, UI element contour detection (buttons, text inputs, panels), and HSV color region extraction.
  - `neron/vision/locator.py`: `ElementLocator` mapping natural language spatial descriptions ("bottom right", "top left", "center") and image templates into precise pixel click coordinates with `ElementNotFoundError` handling.
  - `neron/vision/coordinator.py`: `VisionCoordinator` tying together screen capture, OpenCV visual analysis, locator, and native desktop mouse/keyboard drivers.
  - `neron/tools/vision/`: Registered 4 new capability-gated vision tools:
    - `vision.screenshot` (Capability: `computer.screen`)
    - `vision.find_element` (Capability: `computer.screen`)
    - `vision.click_element` (Capability: `computer.mouse`)
    - `vision.type_text` (Capability: `computer.keyboard`)
  - `neron/core/planner/dag_planner.py`: Extended DAG planner with visual reasoning workflows:
    - Multi-step click-then-type pipelines (`vision.click_element` → `vision.type_text`)
    - Visual click workflows (`vision.find_element` → `vision.click_element`)
    - Single-step screenshot, typing, and on-screen element search
  - `tests/test_vision.py`: 19 new unit and integration tests covering capture, analyzer, locator, coordinator, tools, and DAG planner.

### Test Suite
- **83/83 tests passing** (64 previous + 19 new Stage 8 tests, zero regressions).

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
