#!/bin/bash
set -e

# Docker entrypoint script for promptctl with Ollama integration
# Handles initialization, auto-start mode, and CLI commands
#
# Modes:
#   auto     - Start Ollama + promptctl daemon (default for docker-compose)
#   daemon   - Start only promptctl daemon
#   <cmd>    - Run promptctl command
#   bash     - Drop to shell

# Default repository path
REPO_PATH="${PROMPTCTL_REPO:-/home/promptctl/.promptctl}"
LOG_DIR="/var/log/promptctl"

# Ensure log directory exists
mkdir -p "$LOG_DIR" 2>/dev/null || true

# Function to initialize repository if needed
init_repo() {
    # Ensure correct ownership on data directory
    if [ "$(id -u)" = "0" ]; then
        chown -R promptctl:promptctl "$REPO_PATH" 2>/dev/null || true
    fi
    
    if [ ! -d "$REPO_PATH/.git" ]; then
        echo "[entrypoint] Initializing promptctl repository at $REPO_PATH..."
        # Run as promptctl user if we're root
        if [ "$(id -u)" = "0" ]; then
            su - promptctl -c "cd /app && /usr/bin/python3 /app/promptctl.py --repo '$REPO_PATH' status" > /dev/null 2>&1 || true
        else
            /usr/bin/python3 /app/promptctl.py --repo "$REPO_PATH" status > /dev/null 2>&1 || true
        fi
        echo "[entrypoint] Repository initialized."
    fi
}

# Function to wait for Ollama to be ready
wait_for_ollama() {
    echo "[entrypoint] Waiting for Ollama to be ready..."
    local max_attempts=30
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo "[entrypoint] Ollama is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    echo "[entrypoint] Warning: Ollama did not become ready in time"
    return 1
}

# Function to pull model if not present
ensure_model() {
    local model="${1:-phi3.5}"
    echo "[entrypoint] Checking for model: $model"
    if ! /bin/ollama list 2>/dev/null | grep -q "$model"; then
        echo "[entrypoint] Pulling model $model (this may take a few minutes)..."
        /bin/ollama pull "$model" || echo "[entrypoint] Warning: Could not pull model"
    else
        echo "[entrypoint] Model $model already available"
    fi
}

# Check if git is available
if ! command -v git &> /dev/null; then
    echo "[entrypoint] ERROR: git is not installed in the container" >&2
    exit 1
fi

# Handle different startup modes
case "${1:-auto}" in
    auto)
        # Auto mode: Start everything with supervisor
        echo "============================================"
        echo "  promptctl + Ollama Auto-Start Mode"
        echo "============================================"
        echo ""
        echo "Starting services:"
        echo "  - Ollama API:        http://localhost:11434"
        echo "  - promptctl Socket:  http://localhost:9090"
        echo ""
        echo "Browser extension should connect to port 9090"
        echo "============================================"
        echo ""
        
        # Initialize repo first
        init_repo
        
        # Start supervisor (manages both Ollama and promptctl daemon)
        exec /usr/bin/supervisord -c /etc/supervisor/conf.d/promptctl.conf
        ;;
    
    daemon)
        # Daemon-only mode (expects Ollama to be external)
        echo "[entrypoint] Starting promptctl daemon only..."
        init_repo
        shift
        exec /usr/bin/python3 /app/promptctl.py --repo "$REPO_PATH" daemon --socket --socket-port 9090 "$@"
        ;;
    
    --help|-h)
        exec /usr/bin/python3 /app/promptctl.py --repo "$REPO_PATH" --help
        ;;
    
    save|tag|list|show|status|diff|optimize|chain|evaluate|agent|test|pipeline)
        # promptctl commands
        init_repo
        exec /usr/bin/python3 /app/promptctl.py --repo "$REPO_PATH" "$@"
        ;;
    
    bash|sh)
        # Shell access
        exec /bin/bash
        ;;
    
    *)
        # Unknown command - pass through
        exec "$@"
        ;;
esac
