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
| **8** | **Computer Vision & Screen Reasoning** | Screenshot analysis, UI element detection, visual coordinate fallbacks | 📋 Planned |
| **9** | **Memory Subsystem** | Short-term turn cache, working memory, SQLite semantic fact store, procedural recipes | 📋 Planned |
| **10** | **Plugin Architecture** | Plugin loader, manifest validator, sandboxed dynamic tool registration | 📋 Planned |
| **11** | **Online Integrations** | Modular web search, web browser driver, automated online/offline state detection | 📋 Planned |
| **12** | **Self-Diagnostics & Health System** | `HealthManager`, dependency verifier, microphone/speaker testing, auto-repair hints | 📋 Planned |
| **13** | **Development Agent** | `DeveloperAgent`, source code inspection, test generation, patch drafting | 📋 Planned |
| **14** | **Self-Extension & Update Pipeline** | Sandboxed workspace staging, test-driven validation, one-click rollback | 📋 Planned |
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
- [ ] SQLite-backed structured persistent memory.
- [ ] Semantic knowledge indexing with local embeddings.
- [ ] Working memory session store.
- [ ] Procedural automation recipe manager.
- [ ] User memory inspection and deletion UI/CLI.

### Stage 10: Plugin Architecture
- [ ] Plugin specification and `plugin.json` validator.
- [ ] Dynamic tool and command injection into runtime registry.
- [ ] Extension lifecycle controls (`enable`, `disable`, `reload`).
- [ ] Example community plugins (`spotify`, `vscode`, `system_monitor`).

### Stage 11: Modular Online Integrations
- [ ] Pluggable web search engine (DuckDuckGo, SearXNG, Google).
- [ ] Headless browser automation integration (Playwright).
- [ ] Network status observer with zero-latency offline transition.

### Stage 12: Self-Diagnostics & Health System
- [ ] Comprehensive `HealthManager` environment auditor.
- [ ] Diagnostic command (`neron --diagnose`).
- [ ] Hardware capability evaluator (CPU cores, RAM size, GPU availability).
- [ ] Automated troubleshooting recommendations.

### Stage 13: Developer Agent & Self-Improvement
- [ ] `DeveloperAgent` subsystem for codebase introspection.
- [ ] Automated unit test runner and coverage evaluator.
- [ ] Source code patch generation and syntax validator.
- [ ] Plugin scaffolding generator (`neron plugin create <name>`).

### Stage 14: Sandboxed Self-Update Pipeline
- [ ] Isolated staging workspace creator (`.neron/staging/`).
- [ ] Pre-deployment validation gate (lint + unit test + integration test).
- [ ] User-approval changelog modal.
- [ ] Atomic switch and automated rollback on failure.

### Stage 15: Cross-Platform Packaging & Distribution
- [ ] Windows PyInstaller / InnoSetup packaging.
- [ ] Linux AppImage / debian package build pipelines.
- [ ] Standalone offline installer bundled with core models.
