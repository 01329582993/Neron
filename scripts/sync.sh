#!/usr/bin/env bash
# NERON Automatic Git Synchronization Script
set -e

MESSAGE="$1"
WATCH_MODE="$2"
INTERVAL="${3:-60}"

sync_repo() {
    if [ -n "$(git status --porcelain)" ]; then
        echo "[*] Changes detected. Staging and committing..."
        git add .
        COMMIT_MSG="$MESSAGE"
        if [ -z "$COMMIT_MSG" ]; then
            COMMIT_MSG="auto-sync: $(date '+%Y-%m-%d %H:%M:%S')"
        fi
        git commit -m "$COMMIT_MSG"
        echo "[*] Pushing updates to origin main..."
        git push origin main
        echo "[OK] Repository successfully synced with GitHub!"
    else
        echo "[OK] Working tree clean. Checking remote sync..."
        git push origin main
    fi
}

if [ "$WATCH_MODE" == "--watch" ]; then
    echo "========================================="
    echo "   NERON - Auto-Sync Watcher Active"
    echo "   Checking every $INTERVAL seconds..."
    echo "   Press Ctrl+C to stop."
    echo "========================================="
    while true; do
        sync_repo
        sleep "$INTERVAL"
    done
else
    sync_repo
fi
