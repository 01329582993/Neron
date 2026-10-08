# 📦 NERON Installation & Environment Setup Guide

## 1. System Requirements

### Hardware Recommendations
- **CPU**: 4+ physical cores (Intel Core i5/i7/i9 or AMD Ryzen 5/7/9 or Apple Silicon).
- **RAM**:
  - Minimum: 8 GB (for lightweight local models or cloud provider mode).
  - Recommended: 16 GB+ (to comfortably run 7B/8B local LLMs via Ollama alongside OS automation).
- **Disk Space**:
  - Base Neron core: ~100 MB.
  - With local LLMs (e.g., Llama 3.2 3B or Mistral 7B): ~5 GB to 10 GB.
- **Microphone & Speakers**: Required only if Voice mode is enabled.

### Software Prerequisites
- **Operating Systems**:
  - Windows 10 / Windows 11 (64-bit)
  - Linux (Ubuntu 22.04+ or Debian-based distributions recommended)
  - macOS (Monterey 12+ architecture-ready)
- **Python**: Version 3.10 or newer (tested on Python 3.14).
- **Git**: Installed and available in PATH.

---

## 2. Fast Automated Setup

We provide cross-platform automated bootstrap scripts in the `scripts/` folder:

### On Windows (PowerShell)
```powershell
# Open PowerShell in the project directory
.\scripts\setup.ps1
```

### On Linux / macOS (Bash)
```bash
chmod +x scripts/*.sh
./scripts/setup.sh
```

---

## 3. Manual Installation Step-by-Step

### Step 1: Clone Repository
```bash
git clone https://github.com/your-username/neron.git
cd neron
```

### Step 2: Create a Dedicated Virtual Environment
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Core Dependencies
```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

---

## 4. Setting Up Local AI (Recommended)

Neron is **local-first** and connects seamlessly to local inference backends.

### Setting Up Ollama (Easiest Local LLM)
1. Download and install Ollama from [https://ollama.com](https://ollama.com).
2. Pull a recommended model:
   ```bash
   ollama pull llama3.2:3b
   # or for more capable reasoning:
   ollama pull mistral:7b
   ```
3. Verify Ollama is running:
   ```bash
   curl http://localhost:11434/api/tags
   ```
4. Neron will automatically detect this endpoint and use it as its default offline LLM provider.

---

## 5. Verifying Installation & Health Check

Run Neron's built-in diagnostics command to audit your runtime environment:

```bash
python -m neron --diagnose
```

Expected diagnostic output:
```text
[✓] Python Environment: 3.14.x
[✓] OS Controller: WindowsController (Active)
[✓] System Telemetry: CPU, RAM, Disk monitors active
[✓] Permission Engine: Active (Profile: STANDARD)
[✓] AI Provider: Ollama (http://localhost:11434) detected
[✓] Test Suite: 100% Passed
```

---

## 6. Launching Neron

```bash
# Launch interactive console mode
python -m neron
```
