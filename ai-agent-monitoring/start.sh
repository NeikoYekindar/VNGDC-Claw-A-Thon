#!/bin/sh
set -e

echo "[start] Starting Python agent on port 8081..."
# Force port 8081 via env var in case SDK reads PORT from environment
PORT=8081 python main.py &
PYTHON_PID=$!

echo "[start] Waiting for Python agent to be ready..."
MAX_WAIT=30
i=0
while [ $i -lt $MAX_WAIT ]; do
    if wget -q -O /dev/null "http://127.0.0.1:8081/health" 2>/dev/null; then
        echo "[start] Python agent is ready (pid=$PYTHON_PID)"
        break
    fi
    i=$((i + 1))
    echo "[start] Waiting... ($i/$MAX_WAIT)"
    sleep 1
done

if [ $i -eq $MAX_WAIT ]; then
    echo "[start] WARNING: Python agent did not respond on :8081 after ${MAX_WAIT}s — starting nginx anyway"
fi

# Monitor Python — if it dies, restart it
monitor_python() {
    while true; do
        if ! kill -0 $PYTHON_PID 2>/dev/null; then
            echo "[monitor] Python agent died — restarting..."
            PORT=8081 python main.py &
            PYTHON_PID=$!
        fi
        sleep 5
    done
}
monitor_python &

echo "[start] Starting nginx on port 8080..."
exec nginx -c /app/nginx.conf -g "daemon off;"
