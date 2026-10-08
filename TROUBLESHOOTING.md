# 🔍 NERON Troubleshooting & Diagnostic Guide

When encountering unexpected behavior, Neron provides built-in diagnostics and structured log traces to identify and resolve root causes without guesswork.

---

## 🩺 Step 1: Run Built-In Self-Diagnostics

Before manual debugging, let Neron inspect its own environment:

```bash
python -m neron --diagnose
```

The diagnostic engine checks:
1. Python version and required standard/optional packages.
2. OS controller integration and elevation status.
3. Accessible storage, writable data directories, and database health.
4. Local LLM endpoints (Ollama at `localhost:11434`, llama.cpp).
5. Audio hardware and microphone input availability.

---

## 🛠️ Common Issues & Resolutions

### 1. Local AI Model Not Responding
* **Symptom**: Neron states *"No local LLM available"* or falls back to prompt queue.
* **Cause**: Ollama service is not running or the target model is not pulled.
* **Resolution**:
  1. Verify Ollama is started:
     ```bash
     # In a separate terminal
     ollama serve
     ```
  2. Verify that a model is available:
     ```bash
     ollama list
     ```
  3. If empty, pull a model:
     ```bash
     ollama pull llama3.2:3b
     ```
  4. Ensure `http://localhost:11434` is not blocked by local firewalls.

---

### 2. Permission Denied / Tool Execution Blocked
* **Symptom**: Tool returns `PermissionDeniedError: Capability 'terminal.execute' not granted`.
* **Cause**: Active security profile (e.g. `SAFE` or `STANDARD`) requires explicit user confirmation or blocks the capability.
* **Resolution**:
  - In interactive mode, confirm the security prompt with `y`.
  - To change security modes for a session, configure `config/neron.yaml` or pass the profile flag:
    ```bash
    python -m neron --security POWER_USER
    ```
  - Note: System root folders (`C:\Windows\`, `/etc/`) remain protected even in `POWER_USER` mode.

---

### 3. Emergency Stop Triggered (`CTRL + ALT + N`)
* **Symptom**: Tasks abruptly transition to `CANCELLED`, and mouse/keyboard hooks release.
* **Cause**: The global emergency shortcut was pressed or a cancel signal was dispatched.
* **Resolution**:
  - Review the active task in console:
    ```text
    [EMERGENCY STOP] Active plan cancelled by user.
    ```
  - You can immediately resume new tasks safely. Any orphaned background sub-processes were cleanly terminated.

---

### 4. Audio Input / Microphone Detection Issues
* **Symptom**: Voice recognition does not trigger or returns `AudioInputError`.
* **Cause**: Microphone permission not granted at the OS level or missing audio libraries.
* **Resolution**:
  - **Windows**: Verify that *Microphone access for desktop apps* is toggled ON under *Settings → Privacy & Security → Microphone*.
  - **Linux**: Check PulseAudio/PipeWire status:
    ```bash
    pactl list sources short
    ```
  - In headless or text-only environments, run Neron in text console mode:
    ```bash
    python -m neron --no-voice
    ```

---

### 5. Wayland Desktop Automation (Linux)
* **Symptom**: Mouse movements or window captures fail on Linux.
* **Cause**: Default Wayland security policies prevent arbitrary background synthetic input or screen sniffing.
* **Resolution**:
  - Switch to an X11 session, or ensure `xdg-desktop-portal` and PipeWire screencast permissions are enabled for your user session.

---

## 📜 Inspecting Logs & Audit Records

- **Developer Logs**: Stored in `logs/neron.log` (rotating text file with timestamps and stack traces).
- **Security Audit Database**: Stored in `data/audit.db` (SQLite format). You can inspect past tool calls:
  ```bash
  python -m neron --audit-history
  ```
