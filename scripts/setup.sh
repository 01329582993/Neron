#!/usr/bin/env bash
# NERON Linux / macOS Bootstrap Script
set -e

echo "========================================="
echo "   NERON — Setting Up Development Environment"
echo "========================================="

# 1. Check Python
PYTHON_CMD="python3"
if ! command -v "$PYTHON_CMD" &> /dev/null; then
    PYTHON_CMD="python"
fi

if ! command -v "$PYTHON_CMD" &> /dev/null; then
    echo "[ERROR] Python 3.10+ is required but was not found."
    exit 1
fi

echo "[✓] Found Python: $($PYTHON_CMD --version)"

# 2. Virtual environment
if [ ! -d ".venv" ]; then
    echo "[*] Creating virtual environment (.venv)..."
    "$PYTHON_CMD" -m venv .venv
fi

# 3. Activate
echo "[*] Activating virtual environment..."
source .venv/bin/activate

# 4. Install dependencies
echo "[*] Installing project in editable mode..."
pip install --upgrade pip
pip install -e ".[all]"

# 5. Run tests
echo "[*] Running initial test suite..."
pytest tests/

echo "========================================="
echo "   NERON Setup Complete!"
echo "   Run './scripts/dev.sh' to launch console."
echo "   Run './scripts/test.sh' to run tests."
echo "========================================="
