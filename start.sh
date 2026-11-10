#!/bin/bash
# Road Safety AI — start backend + frontend
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "🚀 Starting Road Safety AI..."

# ── Backend ──────────────────────────────────────────────────────────────────
echo "▶  Starting backend on http://localhost:8000"
cd "$ROOT/backend"
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait until backend is healthy
for i in $(seq 1 20); do
  sleep 1
  if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend is ready"
    break
  fi
  if [ $i -eq 20 ]; then
    echo "❌ Backend failed to start. Check output above."
    kill $BACKEND_PID 2>/dev/null
    exit 1
  fi
done

# ── Frontend ─────────────────────────────────────────────────────────────────
echo "▶  Starting frontend on http://localhost:5173"
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "============================================"
echo "  Road Safety AI is running!"
echo "  Frontend : http://localhost:5173"
echo "  Backend  : http://localhost:8000"
echo "  API Docs : http://localhost:8000/docs"
echo "  Login    : admin@roadsafety.ai / Admin@123"
echo "============================================"
echo ""
echo "Press Ctrl+C to stop both services."

# Trap SIGINT to kill both
trap "echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
