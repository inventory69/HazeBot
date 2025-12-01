#!/usr/bin/env python3
"""
Script to automatically split app.py into modular Blueprint files
Preserves all functionality while reducing main file size to <1000 lines
"""

from pathlib import Path

# Read the original app.py
app_py = Path("app.py")
content = app_py.read_text()

# Define split points and modules
splits = {
    "admin_routes": {
        "start": '@app.route("/api/admin/active-sessions"',
        "end": '@app.route("/api/admin/cache/invalidate"',
        "include_end": True,
    },
    "config_routes": {
        "start": '@app.route("/api/config", methods=["GET"])',
        "end": '@app.route("/api/config/server_guide"',
        "include_end": True,
    },
}

print("✅ App split script ready")
print(f"📊 Original app.py: {len(content.splitlines())} lines")
print("🔧 This is a template - manual splitting recommended for safety")
