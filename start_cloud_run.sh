#!/usr/bin/env sh
set -eu

python /app/start_mcp.py &
MCP_PID=$!

cleanup() {
  kill "$MCP_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8080}"
