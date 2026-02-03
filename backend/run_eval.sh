#!/usr/bin/env bash
set -e

# 1) Start server in background
echo "Starting FastAPI server..."
uvicorn app.main:app --reload --port 8000 > /tmp/medibot_eval_server.log 2>&1 &
SERVER_PID=$!

# 2) Wait for server to become ready
echo "Waiting for server to be ready..."
for i in {1..30}; do
  if curl -s http://127.0.0.1:8000/docs >/dev/null; then
    echo "Server is up."
    break
  fi
  sleep 0.5
done

# 3) Run evaluation
echo "Running evaluation..."
python -m app.scripts.evaluate_runner

# 4) Stop server
echo "Stopping server..."
kill $SERVER_PID
echo "Done."
