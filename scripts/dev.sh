#!/usr/bin/env bash
# NERON Linux / macOS Development Console Launcher
set -e

echo "========================================="
echo "   NERON — Launching Console"
echo "========================================="

if [ -f ".venv/bin/python" ]; then
    .venv/bin/python -m neron "$@"
else
    python3 -m neron "$@"
fi
