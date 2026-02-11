#!/bin/bash
# Stop all UGA Course Scheduler services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[stop]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[warn]${NC} $1"
}

# Kill process by PID file
kill_pid_file() {
    local pidfile="$1"
    local name="$2"

    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            log "Stopping $name (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            rm -f "$pidfile"
        else
            warn "$name not running (stale PID file)"
            rm -f "$pidfile"
        fi
    else
        warn "$name PID file not found"
    fi
}

# Stop Celery worker
kill_pid_file "/tmp/celery-worker.pid" "Celery worker"

# Stop Celery beat
kill_pid_file "/tmp/celerybeat.pid" "Celery beat"

# Stop API server
kill_pid_file "/tmp/uga-api.pid" "API server"

# Also try to kill any remaining celery processes for this project
pkill -f "celery.*src.celery_app" 2>/dev/null || true

# Clean up schedule file
rm -f /tmp/celerybeat-schedule

log "All services stopped"
