#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/venv/bin:${PATH}"
export PYTHONPATH="${PYTHONPATH:-/app}"
export API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
export NEXT_TELEMETRY_DISABLED="${NEXT_TELEMETRY_DISABLED:-1}"

shutdown() {
  echo "[start] Shutting down services..."
  kill "${BACKEND_PID:-0}" "${FRONTEND_PID:-0}" "${NGINX_PID:-0}" 2>/dev/null || true
}
trap shutdown EXIT INT TERM

echo "[start] Master FastAPI backend on 127.0.0.1:8000"
cd /app
uvicorn main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

echo "[start] Master Next.js dashboard on 127.0.0.1:8081"
cd /app/frontend
HOSTNAME=127.0.0.1 PORT=8081 node server.js &
FRONTEND_PID=$!

echo "[start] Nginx public reverse proxy on 0.0.0.0:8080"
nginx -c /etc/nginx/nginx.conf -g "daemon off;" &
NGINX_PID=$!

echo "[start] Services running. backend=${BACKEND_PID} frontend=${FRONTEND_PID} nginx=${NGINX_PID}"
wait -n "${BACKEND_PID}" "${FRONTEND_PID}" "${NGINX_PID}"
