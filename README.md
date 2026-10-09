# 🧠 NERON — Modular Local-First Computer Agent

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()
[![Status](https://img.shields.io/badge/status-v1.0.0--rc1%20%7C%20Stages%200--15%20Complete-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/tests-293%20passed%20%2F%200%20failed-success.svg)]()

> **Neron** is an extensible, local-first AI computer agent and personal operating layer capable of understanding natural language and voice commands, observing desktop screens, controlling applications, managing files, orchestrating system tasks, and evolving safely through a sandboxed self-development loop.

---

## ⚡ Core Philosophy

1. **Local-First by Default**: Core planning, tool execution, memory, and local inference (e.g., via Ollama, llama.cpp) operate entirely offline. Internet access enhances capability (cloud LLMs, web search, browser automation) but is never a hard dependency.
2. **Transparent Permission Engine**: No opaque or unrestricted automation. Every computer action declares required permissions (`filesystem.read`, `terminal.execute`, `computer.mouse`, `system.admin`, etc.). The user chooses their governance mode (`SAFE`, `STANDARD`, `POWER_USER`, or `CUSTOM`) with real-time prompt verification for sensitive operations.
3. **Emergency Stop (`CTRL+ALT+N`)**: Immediate, hard cancellation of active automation runs at both keyboard hook and software levels.
4. **Clean OS Abstraction**: Core decision logic never hard-codes platform semantics. An `OSController` abstraction isolates Windows, Linux, and macOS implementations.
5. **Separation of Planning and Execution**: Tasks pass through an explicit Directed Acyclic Graph (`DAGPlanner` → `DAGExecutor`) with multi-step validation, automatic retries, and rollback capabilities.
6. **Action Verification**: Neron never assumes execution succeeded; it actively verifies environmental state (process lists, window titles, file existence, visual OCR checks).
7. **Controlled Self-Improvement**: A built-in `DeveloperAgent` enables self-diagnosis, test generation, plugin scaffolding, staging workspace validation, and atomic backups with one-click rollback.

---

## 🧩 Architectural Subsystems (Stages 0–15)

| Subsystem | Stage | Core Modules | Key Capabilities |
| :--- | :---: | :--- | :--- |
| **Foundations & Config** | 0 | `neron.config`, `neron.utils` | Hierarchical YAML/JSON configuration, structured logging, audit trails |
| **Security & Permissions** | 1 | `neron.security` | Capability matrix, `PermissionManager`, interactive confirmation, `CTRL+ALT+N` stop |
| **OS Abstraction** | 2 | `neron.os` | Unified `OSController` for Windows, Linux & macOS process/window/telemetry control |
| **PC Automation Tools** | 3 | `neron.tools`, `neron.computer` | File operations, shell execution, window focus/keystrokes, audio volume |
| **Local & Cloud AI** | 4 | `neron.ai` | Provider-agnostic router: Ollama, llama.cpp, OpenAI, Anthropic, offline fallback |
| **Voice Pipeline** | 5 | `neron.voice` | Voice Activity Detection (VAD), "Hey Neron" wake-word, Whisper STT, Piper/System TTS |
| **DAG Planner & Engine** | 6 | `neron.core.planner`, `executor` | Multi-step DAG generation, step-level preconditions, recovery heuristics, state machine |
| **Operating Console UI** | 7 | `neron.ui`, `neron.__main__` | Rich CLI terminal console, live task telemetry, colored audit displays |
| **Computer Vision** | 8 | `neron.vision` | Multi-monitor screenshot capture, OCR text detection, UI element localization |
| **Persistent Memory** | 9 | `neron.memory` | Short-term turn cache, SQLite semantic fact store, procedural recipe recall |
| **Plugin Architecture** | 10 | `neron.plugins` | Dynamic manifest loader (`plugin.yaml`), isolated execution sandbox, hot-reload |
| **Online Integrations** | 11 | `neron.network` | Automated online/offline detection, DuckDuckGo search, headless web driver |
| **Self-Diagnostics** | 12 | `neron.diagnostics` | `HealthManager`, dependency checks, hardware tier profiling, audio device checks |
| **Developer Agent** | 13 | `neron.developer` | AST code introspection, test runner, patch validator, plugin scaffolder |
| **Self-Update & Rollback**| 14 | `neron.developer` | Staged workspace sandbox, syntax/security/test validation gate, atomic backups |
| **Packaging & Distribution**| 15 | `neron.packaging` | PyInstaller spec generator, InnoSetup Windows installer, Linux AppImage/Debian, offline bundle |

---

## 🏗️ Repository Architecture

```text
Neron/
├── neron/
│   ├── ai/                    # Provider-agnostic AI interfaces (Ollama, llama.cpp, Cloud)
│   ├── computer/              # Desktop input automation (mouse, keyboard, window focus)
│   ├── config/                # YAML/JSON unified configuration manager
│   ├── core/                  # Core orchestrator, DAG planner, executor, events, state
│   ├── developer/             # Introspection, staging workspace, validation gate, backup manager
│   ├── diagnostics/           # Self-health diagnostics, hardware tier profiling
│   ├── memory/                # Turn cache, working memory, SQLite semantic fact store
│   ├── network/               # Connectivity monitor, web search, web browser tools
│   ├── os/                    # Platform abstraction layer (Windows, Linux, macOS)
│   ├── packaging/             # PyInstaller specs, Windows/Linux/Offline bundle builders
│   ├── plugins/               # Plugin manager, manifest validator, sandboxed loader
│   ├── security/              # Permission manager, security policy, emergency stop
│   ├── tools/                 # Tool interfaces, registry, filesystem, terminal, system tools
│   ├── ui/                    # Rich desktop console & interactive terminal UI
│   ├── utils/                 # Logging, audit trail, platform helpers
│   ├── vision/                # Screen capture, OCR text extraction, UI element detector
│   ├── voice/                 # Voice pipeline (VAD, Wake Word, Whisper STT, TTS)
│   └── __main__.py            # CLI entrypoint & interactive REPL console
├── tests/                     # 293 comprehensive unit, integration, and mock tests
├── scripts/                   # Cross-platform setup, test, dev, and packaging scripts
├── config/                    # Default configuration templates (default.yaml)
├── docs/                      # Architectural specs, manuals, and developer documentation
├── pyproject.toml             # Project manifest and package definition
└── README.md                  # Project overview
```

---

## 🚀 Quick Start

### 1. Requirements
- **Python**: 3.10+ (tested on Python 3.10 through 3.14)
- **Git**: Installed and available in PATH
- **OS**: Windows 10/11, Ubuntu/Debian Linux, or macOS

### 2. Environment Setup

**Windows (PowerShell):**
```powershell
.\scripts\setup.ps1
```

**Linux / macOS (Bash):**
```bash
chmod +x scripts/*.sh
./scripts/setup.sh
```

---

## 💻 CLI Usage Reference

Neron provides an extensive CLI interface for interactive usage, task execution, diagnostics, development, and packaging:

### 1. Interactive Desktop Console (REPL)
Launch the interactive Rich terminal console:
```bash
python -m neron
```
Inside the console, you can issue conversational instructions or use built-in management commands:
- `status` — Live system telemetry and resource consumption
- `health` — Run immediate self-diagnostics
- `tools` — List all registered tools and their permission capabilities
- `audit` — Inspect recent security decision history
- `mode <MODE>` — Switch security governance mode (`SAFE`, `STANDARD`, `POWER_USER`)
- `stop` — Trigger emergency stop
- `reset-stop` — Reset emergency stop state
- `exit` — Exit Neron

### 2. Direct Goal Execution (One-Shot)
Execute a natural language task and exit immediately upon completion:
```bash
python -m neron -g "open notepad and summarize system status"
```

### 3. System Diagnostics & Health Audit
Check Python runtime, required packages, local Ollama connectivity, network latency, and hardware tiers:
```bash
python -m neron --diagnose
```

### 4. Security Audit Trail
Inspect the recent audit trail of executed tools and permissions:
```bash
python -m neron --audit-history
```

### 5. Automated Developer Test Suite
Run the test runner directly through the Neron developer engine:
```bash
python -m neron --test           # Run entire suite
python -m neron --test tests/test_security.py  # Run targeted test
```

### 6. AST Code Introspection
Inspect the internal structure, classes, functions, and imports of any module or file:
```bash
python -m neron --inspect neron.core.planner.dag_planner
```

### 7. Plugin Scaffolding
Generate a production-ready plugin scaffold with `plugin.yaml`, tool implementations, and test stubs:
```bash
python -m neron plugin create my_custom_tool --desc "Custom automated workflow" --tool custom.run
```

---

## 📦 Packaging & Distribution

Build standalone distribution packages using the Stage 15 packaging pipeline:

### Windows Executable & Installer
```powershell
.\scripts\build_windows.ps1
```
*Generates standalone PyInstaller binaries and customized InnoSetup `.iss` installers.*

### Linux AppImage & Debian Package
```bash
./scripts/build_linux.sh
```
*Generates Freedesktop AppImage bundles and standard `.deb` packages.*

### Zero-Config Offline Bundle
```bash
python scripts/build_offline.py --include-models
```
*Generates a self-contained distribution with bootstrap installers (`install_offline.bat` / `.sh`) and SHA256 integrity validation.*

---

## 🛡️ Permission Modes

| Mode | Allowed Actions | Confirmation Prompt |
| :--- | :--- | :--- |
| **SAFE** | Read-only operations (`filesystem.read`, `system.inspect`, queries) | Required for any state-modifying action |
| **STANDARD** *(Default)* | Typical user workflows, app launching, standard file writes | Prompts for terminal execution, file deletion, administrative changes |
| **POWER_USER** | Broad computer control, script execution, automated multi-step DAGs | Prompts only for administrative (`admin`) and destructive commands |
| **CUSTOM** | Granular user-defined whitelist/blacklist per capability | User configured |

---

## 🧪 Test Suite

The entire system is continuously verified through an exhaustive test suite:
```bash
# Run pytest across all subsystems
pytest
```
**Current Status**: `293 passed` in ~31s, 0 failures, 100% test pass rate across Stages 0–15.

---

## 📚 Documentation Index

- [Architecture Specification (ARCHITECTURE.md)](ARCHITECTURE.md)
- [Staged Development Roadmap (ROADMAP.md)](ROADMAP.md)
- [Security & Permission Model (SECURITY.md)](SECURITY.md)
- [Installation Guide (INSTALLATION.md)](INSTALLATION.md)
- [Plugin Development Guide (PLUGIN_DEVELOPMENT.md)](PLUGIN_DEVELOPMENT.md)
- [Developer Agent & Self-Improvement Loop (DEVELOPMENT_AGENT.md)](DEVELOPMENT_AGENT.md)
- [Troubleshooting & Diagnostics (TROUBLESHOOTING.md)](TROUBLESHOOTING.md)
- [Contributing Guidelines (CONTRIBUTING.md)](CONTRIBUTING.md)
- [Changelog (CHANGELOG.md)](CHANGELOG.md)

---

## 📄 License
MIT License. See [LICENSE](LICENSE) for details.
