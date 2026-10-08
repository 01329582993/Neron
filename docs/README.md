# 🧠 NERON — Modular Local-First Computer Agent

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()
[![Status](https://img.shields.io/badge/status-Stage%201%20%26%202%20Core%20%2B%20OS%20Abstraction-orange.svg)]()

> **Neron** is an extensible, local-first AI computer agent and personal operating layer capable of understanding natural language and voice commands, observing desktop screens, controlling applications, managing files, orchestrating system tasks, and learning new capabilities through a sandboxed development loop.

---

## ⚡ Core Philosophy

1. **Local-First by Default**: Core planning, tool execution, memory, and local inference (e.g., via Ollama, llama.cpp) operate entirely offline. Internet access enhances capability (cloud LLMs, web search, online APIs) but is never a hard dependency.
2. **Transparent Permission Engine**: No opaque or unrestricted automation. Every computer action declares required permissions (`filesystem.read`, `terminal.execute`, `computer.mouse`, `system.admin`, etc.). The user chooses their governance mode (`SAFE`, `STANDARD`, `POWER_USER`, or `CUSTOM`) with real-time prompt verification for sensitive operations.
3. **Emergency Stop (`CTRL+ALT+N`)**: Immediate, hard cancellation of active automation runs at both keyboard and software levels.
4. **Clean OS Abstraction**: Core decision logic never hard-codes platform semantics. An `OSController` abstraction isolates Linux, Windows, and macOS implementations.
5. **Separation of Planning and Execution**: Tasks pass through explicit lifecycles (`PENDING` → `PLANNING` → `WAITING_FOR_PERMISSION` → `EXECUTING` → `VERIFYING` → `COMPLETED` / `FAILED` / `CANCELLED`).
6. **Action Verification**: Neron does not assume execution succeeded; it verifies state (process lists, window titles, file existence, visual checks).
7. **Controlled Self-Improvement**: A dedicated `DeveloperAgent` enables self-diagnosis, test generation, and plugin scaffolding within isolated development workspaces rather than unconstrained runtime self-modification.

---

## 🏗️ Repository Architecture

```text
Neron/
├── neron/
│   ├── core/                  # Core orchestrator, planner, executor, events, context, state
│   ├── ai/                    # Provider-agnostic AI interfaces (LLM, Vision, Embeddings)
│   ├── voice/                 # Voice pipeline (VAD, Wake Word, STT, TTS)
│   ├── computer/              # Desktop controls (Mouse, Keyboard, Screen, Window manager)
│   ├── tools/                 # Tool interfaces, registry, filesystem, terminal, system tools
│   ├── os/                    # Platform abstraction layer (Windows, Linux, macOS)
│   ├── plugins/               # Plugin manager, manifest loader, sandboxed extension API
│   ├── security/              # Permission manager, security policy, emergency stop
│   ├── diagnostics/           # Self-health monitor, dependency checker, diagnostics engine
│   ├── dev_agent/             # Sandboxed self-extension & maintenance agent
│   ├── ui/                    # Desktop operating console & tray manager
│   ├── config/                # YAML/JSON unified configuration manager
│   └── utils/                 # Logging, audit trail, platform helpers
├── tests/                     # Unit, integration, and mock tool test suites
├── scripts/                   # Cross-platform setup, dev, test, and build automation
├── config/                    # Default configurations
├── docs/                      # Architectural specs and developer manuals
├── pyproject.toml             # Project manifest and package definition
└── README.md                  # Project overview
```

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+ (tested on Python 3.14)
- Git
- Windows 10/11 or Ubuntu/Debian Linux (macOS architecture-ready)

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

### 3. Run Self-Diagnostics & Tests
```powershell
# Run the test suite
.\scripts\test.ps1

# Check system health and provider connectivity
python -m neron --diagnose
```

### 4. Launch Neron Console
```powershell
# Start Neron in interactive console mode
python -m neron
```

---

## 🛡️ Permission Modes

| Mode | Allowed Actions | Confirmation Prompt |
| :--- | :--- | :--- |
| **SAFE** | Read-only operations (`filesystem.read`, `system.inspect`, queries) | Required for any state-modifying action |
| **STANDARD** *(Default)* | Typical user workflows, app launching, standard file writes | Prompts for terminal execution, file deletion, system configuration |
| **POWER_USER** | Broad computer control, script execution, automated tasks | Prompts only for administrative (`admin`) and destructive commands |
| **CUSTOM** | Granular user-defined whitelist/blacklist per capability | User configured |

---

## 📚 Documentation Index

- [Architecture Specification (ARCHITECTURE.md)](docs/ARCHITECTURE.md)
- [Staged Development Roadmap (ROADMAP.md)](docs/ROADMAP.md)
- [Security & Permission Model (SECURITY.md)](docs/SECURITY.md)
- [Installation Guide (INSTALLATION.md)](docs/INSTALLATION.md)
- [Plugin Development Guide (PLUGIN_DEVELOPMENT.md)](docs/PLUGIN_DEVELOPMENT.md)
- [Developer Agent & Self-Improvement Loop (DEVELOPMENT_AGENT.md)](docs/DEVELOPMENT_AGENT.md)
- [Contributing Guidelines (CONTRIBUTING.md)](docs/CONTRIBUTING.md)
- [Troubleshooting & Diagnostics (TROUBLESHOOTING.md)](docs/TROUBLESHOOTING.md)
- [Changelog (CHANGELOG.md)](docs/CHANGELOG.md)

---

## 📄 License
MIT License. See [LICENSE](LICENSE) for details.
