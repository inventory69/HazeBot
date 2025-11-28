"""
Audit logging helpers for the HazeBot API.
"""

import json
import sys
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import request

# Ensure we can import the root-level Config module (for paths)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from Utils.Logger import Logger  # noqa: E402


def log_action(username, action, details=None):
    """Log user actions to file and console."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "username": username,
        "action": action,
        "details": details or {},
    }

    Logger.info(f"🔧 [API Action] {username} - {action}" + (f" | {details}" if details else ""))

    audit_log_path = Path(__file__).parent.parent.parent / "Logs" / "api_audit.log"
    audit_log_path.parent.mkdir(exist_ok=True)

    with open(audit_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")


def log_config_action(config_name):
    """Decorator to automatically log configuration changes."""

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if request.method in ["PUT", "POST"] and request.is_json:
                data = request.get_json()
                action_type = "update" if request.method == "PUT" else "reset" if "reset" in request.path else "action"
                log_action(
                    request.username,
                    f"{action_type}_{config_name}_config",
                    {"keys_modified": list(data.keys()) if data else []},
                )
            elif request.method == "POST" and "reset" in request.path:
                log_action(request.username, f"reset_{config_name}_config", {"status": "reset to defaults"})

            return f(*args, **kwargs)

        return wrapper

    return decorator
