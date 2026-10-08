#!/usr/bin/env bash
# NERON Linux / macOS Test Runner Script
set -e

echo "========================================="
echo "   NERON — Running Automated Test Suite"
echo "========================================="

if [ -f ".venv/bin/pytest" ]; then
    .venv/bin/pytest tests/ -v
else
    pytest tests/ -v
fi

echo "[✓] All tests passed cleanly!"
