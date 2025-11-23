#!/usr/bin/env fish
# Cleanup script to kill processes on port 5070 (Fish shell version)

set PORT 5070

echo "🔍 Checking for processes on port $PORT..."

# Find PID using the port
set PID (lsof -ti :$PORT 2>/dev/null)

if test -z "$PID"
    echo "✅ Port $PORT is free"
    exit 0
end

echo "⚠️  Found process(es) on port $PORT: $PID"
echo "🔨 Killing process(es)..."

# Kill the process
kill -9 $PID 2>/dev/null

# Wait a moment
sleep 1

# Verify
if lsof -ti :$PORT >/dev/null 2>&1
    echo "❌ Failed to free port $PORT"
    exit 1
else
    echo "✅ Port $PORT is now free"
    exit 0
end
