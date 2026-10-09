# 🗺️ NERON Staged Development Roadmap

This roadmap defines the sequential milestones for building Neron. In accordance with Core Philosophy #2, **we do not build everything at once**; each stage builds upon verified, tested components from preceding stages.

---

## 🧭 Milestone Matrix

| Stage | Name | Target Capabilities | Status |
| :---: | :--- | :--- | :---: |
| **0** | **Architecture & Repository Foundations** | Complete architecture spec, config schema, event bus, logging, repo setup | ✅ **Complete** |
| **1** | **Core Infrastructure & Security Engine** | Core agent contracts, TaskPlanner interfaces, Executor state machine, PermissionManager, EmergencyStop | ✅ **Complete** |
| **2** | **OS Abstraction Layer** | Abstract `OSController`, `WindowsController`, `LinuxController`, process/window/telemetry detection | ✅ **Complete** |
| **3** | **Basic PC Tools** | Filesystem search/read/write, terminal command executor, system volume, app launcher, verification hooks | ✅ **Complete** |
| **4** | **Local LLM Integration** | `LLMProvider` abstraction, Ollama & llama.cpp connectors, offline-first fallback router | ✅ **Complete** |
| **5** | **Voice Pipeline** | Modular VAD, wake-word engine ("Hey Neron"), Whisper STT, Piper/System TTS | ✅ **Complete** |
| **6** | **Task Planning & Execution Engine** | Multi-step DAG planning, verification loops, retry/rollback, failure analysis | ✅ **Complete** |
| **7** | **Desktop Operating Console & UI** | Rich terminal console, active task monitor, plan step breakdown, failure hints | ✅ **Complete** |
| **8** | **Computer Vision & Screen Reasoning** | Screenshot analysis, UI element detection, visual coordinate fallbacks | ✅ **Complete** |
| **9** | **Memory Subsystem** | Short-term turn cache, working memory, SQLite semantic fact store, procedural recipes | ✅ **Complete** |
| **10** | **Plugin Architecture** | Plugin loader, manifest validator, sandboxed dynamic tool registration | ✅ **Complete** |
| **11** | **Online Integrations** | Modular web search, web browser driver, automated online/offline state detection | ✅ **Complete** |
| **12** | **Self-Diagnostics & Health System** | `HealthManager`, dependency verifier, microphone/speaker testing, auto-repair hints | ✅ **Complete** |
| **13** | **Development Agent** | `DeveloperAgent`, source code inspection, test generation, patch drafting | ✅ **Complete** |
| **14** | **Self-Extension & Update Pipeline** | Sandboxed workspace staging, test-driven validation, one-click rollback | ✅ **Complete** |
| **15** | **Cross-Platform Packaging** | Windows executable/installer, Linux AppImage/package, zero-config distributions | 📋 Planned |

---

## 📌 Detailed Stage Breakdown

### Stage 0: Architecture & Foundations (Current Baseline)
- [x] Initial repository structure and Git configuration.
- [x] Project documentation suite (`README.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `SECURITY.md`, etc.).
- [x] Unified configuration schema (`neron/config/`).
- [x] Cross-platform build and automation scripts (`scripts/`).
- [x] Testing framework setup (`pytest`).

### Stage 1: Core Infrastructure & Security Engine
- [x] Asynchronous pub/sub `EventBus` (`neron/core/events/`).
- [x] Structured task state machine:
  `PENDING` → `PLANNING` → `WAITING_FOR_PERMISSION` → `EXECUTING` → `VERIFYING` → `COMPLETED` / `FAILED` / `CANCELLED`.
- [x] `PermissionManager` with `SAFE`, `STANDARD`, `POWER_USER`, and `CUSTOM` policies.
- [x] Global `EmergencyStop` coordinator with cancellation propagation.
- [x] Structured logger and audit trail recorder.

### Stage 2: OS Abstraction Layer
- [x] `OSController` abstract interface.
- [x] `WindowsController` implementation (using PowerShell, native Win32 APIs, psutil).
- [x] `LinuxController` implementation (using DBus, procfs, xdotool/wayland, psutil).
- [x] `MacOSController` stub (architecture-ready).
- [x] Real-time hardware telemetry (CPU, RAM, Disk, Battery, Network status).
- [x] Process and Window state introspection.

### Stage 3: Foundational PC Tools & Tool Registry
- [x] `BaseTool` contract and validation engine.
- [x] Central `ToolRegistry` with filter, lookup, and permission validation.
- [x] Filesystem tools (`filesystem.search`, `filesystem.read`, `filesystem.write`, `filesystem.list`, `filesystem.delete`).
- [x] Terminal tool (`terminal.execute` with timeout and sandboxed workdir).
- [x] System tools (`system.telemetry`, `system.volume`, `system.open_app`, `system.close_app`).
- [x] State verification hooks for every mutation tool.

### Stage 4: Local LLM Integration & Offline AI
- [x] `LLMProvider` contract (`generate`, `chat`, `stream`, `tools`).
- [x] `OllamaProvider` implementation with auto-model discovery.
- [x] `LlamaCppProvider` architecture ready.
- [x] `OpenAICompatibleProvider` for local servers (LM Studio, vLLM) and cloud APIs.
- [x] `AIRouter` with automated offline fallback and network reachability probing.

### Stage 5: Voice Pipeline
- [x] Audio capture abstraction (`AudioDeviceManager`).
- [x] Low-overhead Voice Activity Detection.
- [x] Wake-word detector ("Hey Neron").
- [x] Local Speech-to-Text via Whisper (`faster-whisper` / fallback).
- [x] Local Text-to-Speech via Piper or OS speech synthesizers.
- [x] Push-to-talk and voice emergency stop triggers.

### Stage 6: Task Planning & Execution Engine
- [x] Single-turn vs. multi-step intent classifier.
- [x] Step planner creating directed task graphs.
- [x] Step execution coordinator with dependency resolution.
- [x] Automated post-action verification and error recovery branching.

### Stage 7: Desktop Console & User Interface
- [x] Local-first desktop operating console.
- [x] Real-time activity timeline and task visualizer.
- [x] System tray daemon with background monitoring.
- [x] Interactive permission confirmation dialogs and emergency cancel button.

### Stage 8: Computer Vision & Screen Reasoning
- [x] Cross-platform screen capture (`ScreenCapture`, MSS + Pillow ImageGrab fallback).
- [x] Screen element localization (`ScreenAnalyzer`, OpenCV template matching with NMS).
- [x] Structured screen analysis before and after GUI actions (`ElementLocator` spatial heuristics).
- [x] Visual coordinate automation tools (`vision.screenshot`, `vision.find_element`, `vision.click_element`, `vision.type_text`).


### Stage 9: Memory Subsystem
- [x] SQLite-backed structured persistent memory (`SQLiteMemoryStore`).
- [x] Full-text search and knowledge indexing (SQLite FTS5 + LIKE fallback).
- [x] Working memory session store (`WorkingMemory` volatile scratchpad & variables).
- [x] Procedural automation recipe manager (`RecipeManager` DAG workflow templates).
- [x] User memory tools and natural language commands (`memory.remember`, `memory.recall`, `memory.forget`).


### Stage 10: Plugin Architecture
- [x] Plugin specification and `plugin.yaml`/`plugin.json` validator (`PluginManifestValidator`).
- [x] Dynamic tool and command injection into runtime registry (`PluginLoader` and `PluginManager`).
- [x] Extension lifecycle controls (`discover`, `load`, `enable`, `disable`, `reload`).
- [x] Example community plugins (`neron-system-monitor`, `neron-media-controller`).


### Stage 11: Modular Online Integrations
- [x] Pluggable web search engine (`DuckDuckGoProvider`, `SearXNGProvider`, `MockSearchProvider`, `SearchEngineRouter`).
- [x] Web reader and token-efficient content extractor (`WebReader` with BeautifulSoup cleaning).
- [x] Network status observer with zero-latency cached reads (`NetworkObserver` and `network.status_changed` events).
- [x] Built-in online tools (`network.status`, `network.search`, `network.fetch_page`).


### Stage 12: Self-Diagnostics & Health System
- [x] Comprehensive `HealthManager` environment auditor.
- [x] Diagnostic command (`neron --diagnose`).
- [x] Hardware capability evaluator (CPU cores, RAM size, GPU availability).
- [x] Automated troubleshooting recommendations.

### Stage 13: Developer Agent & Self-Improvement
- [x] `DeveloperAgent` subsystem for codebase introspection.
- [x] Automated unit test runner and coverage evaluator.
- [x] Source code patch generation and syntax validator.
- [x] Plugin scaffolding generator (`neron plugin create <name>`).

### Stage 14: Sandboxed Self-Update Pipeline
- [x] Isolated staging workspace creator (`.neron/staging/`).
- [x] Pre-deployment validation gate (lint + unit test + integration test).
- [x] User-approval changelog modal.
- [x] Atomic switch and automated rollback on failure.

### Stage 15: Cross-Platform Packaging & Distribution
- [ ] Windows PyInstaller / InnoSetup packaging.
- [ ] Linux AppImage / debian package build pipelines.
- [ ] Standalone offline installer bundled with core models.
