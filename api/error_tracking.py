"""
Error Tracking System for API
Captures, aggregates, and stores error/exception data for monitoring
"""

import json
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
import hashlib

logger = logging.getLogger(__name__)


class ErrorTracker:
    """Handles error tracking and aggregation"""

    def __init__(self, error_file: Path):
        self.error_file = error_file
        self.data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        """Load error data from file"""
        if self.error_file.exists():
            try:
                with open(self.error_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load error data: {e}")
                return self._get_empty_structure()
        return self._get_empty_structure()

    def _get_empty_structure(self) -> Dict[str, Any]:
        """Return empty error data structure"""
        return {
            "errors": [],
            "error_groups": {},
            "daily_error_counts": {},
            "last_updated": datetime.utcnow().isoformat()
        }

    def _save_data(self):
        """Save error data to file"""
        try:
            self.error_file.parent.mkdir(parents=True, exist_ok=True)
            self.data["last_updated"] = datetime.utcnow().isoformat()
            with open(self.error_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save error data: {e}")

    def _generate_error_signature(self, error_type: str, message: str, endpoint: str) -> str:
        """Generate unique signature for error grouping"""
        # Use first line of message for grouping (ignore dynamic parts)
        message_first_line = message.split('\n')[0][:100]
        signature_str = f"{error_type}:{endpoint}:{message_first_line}"
        return hashlib.md5(signature_str.encode()).hexdigest()[:16]

    def track_error(
        self,
        error_type: str,
        message: str,
        endpoint: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        stacktrace: Optional[str] = None,
        request_data: Optional[Dict] = None
    ) -> None:
        """
        Track an error occurrence
        
        Args:
            error_type: Exception type (e.g., "KeyError", "ValueError")
            message: Error message
            endpoint: API endpoint where error occurred
            user_id: Discord ID of user (if applicable)
            username: Username (if applicable)
            stacktrace: Full stacktrace
            request_data: Additional request context
        """
        now = datetime.utcnow()
        today = now.date().isoformat()

        # Generate error signature for grouping
        signature = self._generate_error_signature(error_type, message, endpoint)

        # Create error entry
        error_entry = {
            "timestamp": now.isoformat(),
            "error_type": error_type,
            "message": message,
            "endpoint": endpoint,
            "user_id": user_id,
            "username": username,
            "stacktrace": stacktrace,
            "request_data": request_data,
            "signature": signature
        }

        # Add to errors list (keep last 1000)
        self.data["errors"].append(error_entry)
        if len(self.data["errors"]) > 1000:
            self.data["errors"] = self.data["errors"][-1000:]

        # Update error groups (for aggregation)
        if signature not in self.data["error_groups"]:
            self.data["error_groups"][signature] = {
                "error_type": error_type,
                "message": message.split('\n')[0][:200],  # First line only
                "endpoint": endpoint,
                "first_seen": now.isoformat(),
                "last_seen": now.isoformat(),
                "count": 0,
                "affected_users": set()
            }

        group = self.data["error_groups"][signature]
        group["count"] += 1
        group["last_seen"] = now.isoformat()
        
        # Track affected users (convert set to list for JSON)
        if isinstance(group["affected_users"], list):
            affected_users = set(group["affected_users"])
        else:
            affected_users = group["affected_users"]
        
        if user_id:
            affected_users.add(user_id)
        group["affected_users"] = list(affected_users)

        # Update daily error counts
        if today not in self.data["daily_error_counts"]:
            self.data["daily_error_counts"][today] = 0
        self.data["daily_error_counts"][today] += 1

        self._save_data()
        logger.debug(f"Tracked error: {error_type} in {endpoint}")

    def get_error_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get error summary for dashboard"""
        now = datetime.utcnow()
        cutoff = now - timedelta(days=days)

        # Filter recent errors
        recent_errors = [
            e for e in self.data["errors"]
            if datetime.fromisoformat(e["timestamp"]) > cutoff
        ]

        # Get top error groups
        error_groups_list = []
        for signature, group in self.data["error_groups"].items():
            if datetime.fromisoformat(group["last_seen"]) > cutoff:
                error_groups_list.append({
                    "signature": signature,
                    **group
                })

        # Sort by count
        error_groups_list.sort(key=lambda x: x["count"], reverse=True)

        # Get daily error trend
        daily_trend = {}
        for i in range(days):
            date = (now - timedelta(days=i)).date().isoformat()
            daily_trend[date] = self.data["daily_error_counts"].get(date, 0)

        return {
            "total_errors": len(recent_errors),
            "unique_error_types": len(error_groups_list),
            "top_errors": error_groups_list[:10],
            "recent_errors": recent_errors[-50:],  # Last 50 errors
            "daily_trend": daily_trend,
            "error_rate_per_hour": len(recent_errors) / (days * 24) if days > 0 else 0
        }

    def cleanup_old_errors(self, days_to_keep: int = 30) -> int:
        """Remove errors older than specified days"""
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
        original_count = len(self.data["errors"])

        self.data["errors"] = [
            e for e in self.data["errors"]
            if datetime.fromisoformat(e["timestamp"]) > cutoff
        ]

        # Cleanup error groups with no recent occurrences
        groups_to_remove = []
        for signature, group in self.data["error_groups"].items():
            if datetime.fromisoformat(group["last_seen"]) < cutoff:
                groups_to_remove.append(signature)

        for signature in groups_to_remove:
            del self.data["error_groups"][signature]

        removed = original_count - len(self.data["errors"])
        if removed > 0:
            self._save_data()
            logger.info(f"Cleaned up {removed} old errors (older than {days_to_keep} days)")

        return removed


def track_api_error(
    error_tracker: ErrorTracker,
    exception: Exception,
    endpoint: str,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    request_data: Optional[Dict] = None
) -> None:
    """
    Helper function to track an API error
    
    Args:
        error_tracker: ErrorTracker instance
        exception: The exception that was caught
        endpoint: API endpoint where error occurred
        user_id: Discord ID of user (if applicable)
        username: Username (if applicable)
        request_data: Additional request context
    """
    error_type = type(exception).__name__
    message = str(exception)
    stacktrace = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))

    error_tracker.track_error(
        error_type=error_type,
        message=message,
        endpoint=endpoint,
        user_id=user_id,
        username=username,
        stacktrace=stacktrace,
        request_data=request_data
    )
