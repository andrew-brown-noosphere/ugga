#!/bin/bash
# Start all UGA Course Scheduler services
#
# Usage:
#   ./scripts/start.sh          # Start all services
#   ./scripts/start.sh api      # Start only the API
#   ./scripts/start.sh worker   # Start only Celery worker
#   ./scripts/start.sh beat     # Start only Celery beat
#   ./scripts/start.sh frontend # Start only frontend

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[start]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[warn]${NC} $1"
}

error() {
    echo -e "${RED}[error]${NC} $1"
}

# Check if Redis is running
check_redis() {
    if ! redis-cli ping > /dev/null 2>&1; then
        warn "Redis is not running. Celery requires Redis."
        warn "Start Redis with: brew services start redis (macOS) or redis-server"
        return 1
    fi
    log "Redis is running"
    return 0
}

# Check if PostgreSQL is running
check_postgres() {
    if ! pg_isready > /dev/null 2>&1; then
        warn "PostgreSQL is not running."
        warn "Start with: brew services start postgresql (macOS)"
        return 1
    fi
    log "PostgreSQL is running"
    return 0
}

# Start the FastAPI backend
start_api() {
    log "Starting API server on port 8000..."
    cd "$PROJECT_DIR"
    python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
}

# Start Celery worker
start_worker() {
    log "Starting Celery worker..."
    cd "$PROJECT_DIR"
    celery -A src.celery_app worker \
        --loglevel=info \
        --concurrency=2 \
        -Q default,scanner
}

# Start Celery beat scheduler
start_beat() {
    log "Starting Celery beat scheduler..."
    cd "$PROJECT_DIR"
    celery -A src.celery_app beat \
        --loglevel=info \
        --pidfile=/tmp/celerybeat.pid \
        --schedule=/tmp/celerybeat-schedule
}

# Start frontend dev server
start_frontend() {
    log "Starting frontend dev server..."
    cd "$PROJECT_DIR/frontend"
    npm run dev
}

# Start all services in background with logging
start_all() {
    log "Starting all UGA Course Scheduler services..."

    # Check dependencies
    check_redis || exit 1
    check_postgres || exit 1

    # Create logs directory
    mkdir -p "$PROJECT_DIR/logs"

    log "Starting Celery worker..."
    celery -A src.celery_app worker \
        --loglevel=info \
        --concurrency=2 \
        -Q default,scanner \
        --pidfile=/tmp/celery-worker.pid \
        > logs/celery-worker.log 2>&1 &
    WORKER_PID=$!
    echo $WORKER_PID > /tmp/celery-worker.pid
    log "Celery worker started (PID: $WORKER_PID)"

    log "Starting Celery beat..."
    celery -A src.celery_app beat \
        --loglevel=info \
        --pidfile=/tmp/celerybeat.pid \
        --schedule=/tmp/celerybeat-schedule \
        > logs/celery-beat.log 2>&1 &
    BEAT_PID=$!
    log "Celery beat started (PID: $BEAT_PID)"

    # Give workers a moment to start
    sleep 2

    log "Starting API server..."
    python -m uvicorn src.api.main:app \
        --reload \
        --host 0.0.0.0 \
        --port 8000 \
        > logs/api.log 2>&1 &
    API_PID=$!
    echo $API_PID > /tmp/uga-api.pid
    log "API server started (PID: $API_PID)"

    echo ""
    log "All services started!"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  API:           ${GREEN}http://localhost:8000${NC}"
    echo -e "  API Docs:      ${GREEN}http://localhost:8000/docs${NC}"
    echo -e "  Logs:          ${YELLOW}$PROJECT_DIR/logs/${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "To stop all services: ./scripts/stop.sh"
    echo "To view logs: tail -f logs/*.log"
}

# Handle command line arguments
case "${1:-all}" in
    api)
        check_postgres || exit 1
        start_api
        ;;
    worker)
        check_redis || exit 1
        start_worker
        ;;
    beat)
        check_redis || exit 1
        start_beat
        ;;
    frontend)
        start_frontend
        ;;
    all)
        start_all
        ;;
    *)
        echo "Usage: $0 {all|api|worker|beat|frontend}"
        exit 1
        ;;
esac
