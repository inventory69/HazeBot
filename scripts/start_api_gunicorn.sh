#!/bin/bash
# Start HazeBot API with Gunicorn (production-ready)

# Get port from environment or default to 5070
PORT="${API_PORT:-5070}"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🌐 Starting HazeBot API with Gunicorn on port $PORT"
echo "📁 Working directory: $SCRIPT_DIR"

# Start Gunicorn with 4 sync workers (thread-safe, handles concurrent requests)
cd "$SCRIPT_DIR"
gunicorn \
    --bind "0.0.0.0:$PORT" \
    --workers 4 \
    --worker-class sync \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    api.app:app
