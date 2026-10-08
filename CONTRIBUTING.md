# 🤝 Contributing to NERON

Thank you for your interest in contributing to **Neron**! Neron is designed as a serious, extensible, local-first computer operating layer. To maintain software integrity and stability, all contributions must adhere to these guidelines.

---

## 📜 The Golden Rules of Neron Development

Before writing code, familiarize yourself with our core principles:

1. **Inspect before changing**: Understand existing contracts and interfaces before modifying them.
2. **Never blindly overwrite working code**: Ensure regressions are prevented with automated tests.
3. **No fake implementations (Section 39)**: If a feature is not yet functional, declare it honestly. Do not create placeholder buttons or mock functions that pretend to perform actions they do not.
4. **Isolate OS-specific code**: The core planning, AI, and tool logic must never directly invoke Windows or Linux API calls. Platform code belongs strictly in `neron/os/<platform>/`.
5. **Always write tests**: Every tool, parser, and controller must have comprehensive unit and integration tests.
6. **Graceful degradation**: Handle missing dependencies (such as missing audio hardware, offline network, or missing local LLMs) with informative error messages.
7. **Security first**: Every tool must declare its required permissions and adhere to permission checks.

---

## 🛠️ Development Setup

### 1. Clone & Initialize
```bash
git clone https://github.com/your-username/neron.git
cd neron
```

### 2. Set Up Virtual Environment

**Windows:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

### 3. Run the Test Suite
```bash
pytest
```
Ensure all tests pass before making any modifications.

---

## 🧩 Adding a New Tool

All tools must subclass `neron.tools.base.BaseTool`:

```python
from typing import Dict, Any, List
from neron.tools.base import BaseTool, ToolResult

class MyCustomTool(BaseTool):
    @property
    def name(self) -> str:
        return "custom.my_tool"

    @property
    def description(self) -> str:
        return "Performs an example safe operation."

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target argument"}
            },
            "required": ["target"]
        }

    @property
    def required_permissions(self) -> List[str]:
        return ["filesystem.read"]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        target = arguments.get("target")
        # Perform action
        return ToolResult(success=True, output=f"Processed {target}")

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> bool:
        # Verify that the action succeeded in the OS environment
        return True
```

Register your tool in `neron/tools/registry.py` and write test cases under `tests/test_tools/`.

---

## 🧪 Testing Guidelines

- Place unit tests under `tests/unit/`.
- Place integration tests under `tests/integration/`.
- Use mock tools (`tests/mocks/`) when testing agent planners or executors to avoid triggering real computer modifications during CI.
- Run tests regularly:
  ```bash
  pytest -v --cov=neron
  ```

---

## 📋 Pull Request Checklist

Before submitting a PR, ensure:
- [ ] Code strictly adheres to Python 3.10+ typing annotations.
- [ ] All new functions and classes have clear docstrings.
- [ ] No hardcoded machine-specific file paths or secrets.
- [ ] All tests pass cleanly (`pytest`).
- [ ] Documentation is updated in `docs/` and `CHANGELOG.md`.
- [ ] Missing dependencies are caught gracefully with user-friendly warnings.
