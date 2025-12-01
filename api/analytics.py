"""
Analytics System for App Usage Tracking
Aggregates session data, user stats, and daily metrics
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class AnalyticsAggregator:
    """Handles aggregation and storage of app usage analytics"""

    def __init__(self, analytics_file: Path):
        self.analytics_file = analytics_file
        self.data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        """Load analytics data from file"""
        if self.analytics_file.exists():
            try:
                with open(self.analytics_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load analytics data: {e}")
                return self._get_empty_structure()
        return self._get_empty_structure()

    def _get_empty_structure(self) -> Dict[str, Any]:
        """Return empty analytics data structure"""
        return {"sessions": [], "daily_stats": {}, "user_stats": {}}

    def _save_data(self):
        """Save analytics data to file"""
        try:
            self.analytics_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.analytics_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save analytics data: {e}")

    def start_session(
        self,
        session_id: str,
        discord_id: str,
        username: str,
        device_info: str,
        platform: str,
        app_version: str,
        ip_address: str,
    ) -> None:
        """Record session start"""
        now = datetime.utcnow().isoformat()

        session = {
            "session_id": session_id,
            "discord_id": discord_id,
            "username": username,
            "device_info": device_info,
            "platform": platform,
            "app_version": app_version,
            "started_at": now,
            "ended_at": None,
            "duration_minutes": 0,
            "ip_address": ip_address,
            "screens_visited": [],
            "actions_count": 0,
            "endpoints_used": {},
        }

        self.data["sessions"].append(session)
        self._save_data()
        logger.debug(f"Started session {session_id} for user {username}")

    def update_session(self, session_id: str, endpoint: str, action: str = "API_CALL") -> None:
        """Update session with new activity"""
        for session in reversed(self.data["sessions"]):
            if session["session_id"] == session_id:
                session["actions_count"] += 1

                # Track endpoint usage
                if endpoint not in session["endpoints_used"]:
                    session["endpoints_used"][endpoint] = 0
                session["endpoints_used"][endpoint] += 1

                # Update last activity time (ended_at tracks last activity)
                session["ended_at"] = datetime.utcnow().isoformat()

                self._save_data()
                break

    def end_session(self, session_id: str) -> None:
        """Record session end and calculate duration"""
        for session in reversed(self.data["sessions"]):
            if session["session_id"] == session_id:
                now = datetime.utcnow()
                session["ended_at"] = now.isoformat()

                # Calculate duration
                try:
                    started = datetime.fromisoformat(session["started_at"])
                    duration = (now - started).total_seconds() / 60  # minutes
                    session["duration_minutes"] = round(duration, 2)
                except Exception as e:
                    logger.error(f"Failed to calculate session duration: {e}")

                self._save_data()
                self._update_user_stats(session)
                self._update_daily_stats(session)
                logger.debug(f"Ended session {session_id}, duration: {session['duration_minutes']}min")
                break

    def _update_user_stats(self, session: Dict[str, Any]) -> None:
        """Update aggregated user statistics"""
        discord_id = session["discord_id"]

        if discord_id not in self.data["user_stats"]:
            self.data["user_stats"][discord_id] = {
                "username": session["username"],
                "first_seen": session["started_at"],
                "last_seen": session["ended_at"],
                "total_sessions": 0,
                "total_time_minutes": 0,
                "avg_session_duration": 0,
                "device_history": [],
            }

        user = self.data["user_stats"][discord_id]
        user["username"] = session["username"]  # Update in case of name change
        user["last_seen"] = session["ended_at"]
        user["total_sessions"] += 1
        user["total_time_minutes"] += session["duration_minutes"]
        user["avg_session_duration"] = round(user["total_time_minutes"] / user["total_sessions"], 2)

        # Track device history (unique devices)
        if session["device_info"] not in user["device_history"]:
            user["device_history"].append(session["device_info"])

        self._save_data()

    def _update_daily_stats(self, session: Dict[str, Any]) -> None:
        """Update daily statistics"""
        try:
            date = datetime.fromisoformat(session["started_at"]).date().isoformat()
        except Exception:
            date = datetime.utcnow().date().isoformat()

        if date not in self.data["daily_stats"]:
            self.data["daily_stats"][date] = {
                "unique_users": set(),
                "total_sessions": 0,
                "total_actions": 0,
                "total_duration_minutes": 0,
                "avg_session_duration": 0,
            }

        stats = self.data["daily_stats"][date]

        # Handle set for unique users (convert to list for JSON)
        if isinstance(stats["unique_users"], list):
            unique_users = set(stats["unique_users"])
        else:
            unique_users = stats["unique_users"]

        unique_users.add(session["discord_id"])
        stats["unique_users"] = list(unique_users)  # Convert back to list for JSON

        stats["total_sessions"] += 1
        stats["total_actions"] += session["actions_count"]
        stats["total_duration_minutes"] += session["duration_minutes"]
        stats["avg_session_duration"] = round(stats["total_duration_minutes"] / stats["total_sessions"], 2)

        self._save_data()

    def add_screen_visit(self, session_id: str, screen_name: str) -> None:
        """Track screen visit in session"""
        for session in reversed(self.data["sessions"]):
            if session["session_id"] == session_id:
                if screen_name not in session["screens_visited"]:
                    session["screens_visited"].append(screen_name)
                self._save_data()
                break

    def get_export_data(self, days: int = None) -> Dict[str, Any]:
        """Export analytics data for external analysis"""
        if days is None:
            return self.data

        # Filter sessions by date
        cutoff = datetime.utcnow() - timedelta(days=days)
        filtered_sessions = [s for s in self.data["sessions"] if datetime.fromisoformat(s["started_at"]) > cutoff]

        # Filter daily stats by date
        cutoff_date = cutoff.date().isoformat()
        filtered_daily = {date: stats for date, stats in self.data["daily_stats"].items() if date >= cutoff_date}

        return {
            "sessions": filtered_sessions,
            "daily_stats": filtered_daily,
            "user_stats": self.data["user_stats"],
            "export_date": datetime.utcnow().isoformat(),
            "days_included": days,
        }

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for dashboard"""
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        # Count active users
        active_7d = sum(
            1 for user in self.data["user_stats"].values() if datetime.fromisoformat(user["last_seen"]) > week_ago
        )
        active_30d = sum(
            1 for user in self.data["user_stats"].values() if datetime.fromisoformat(user["last_seen"]) > month_ago
        )

        # Recent sessions stats
        recent_sessions = [s for s in self.data["sessions"] if datetime.fromisoformat(s["started_at"]) > week_ago]

        total_sessions_7d = len(recent_sessions)
        avg_duration_7d = (
            sum(s["duration_minutes"] for s in recent_sessions) / total_sessions_7d if total_sessions_7d > 0 else 0
        )

        return {
            "total_users": len(self.data["user_stats"]),
            "active_users_7d": active_7d,
            "active_users_30d": active_30d,
            "total_sessions": len(self.data["sessions"]),
            "total_sessions_7d": total_sessions_7d,
            "avg_session_duration_7d": round(avg_duration_7d, 2),
            "last_updated": datetime.utcnow().isoformat(),
        }

    def cleanup_old_sessions(self, days_to_keep: int = 90) -> int:
        """Remove sessions older than specified days to prevent file bloat"""
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
        original_count = len(self.data["sessions"])

        self.data["sessions"] = [s for s in self.data["sessions"] if datetime.fromisoformat(s["started_at"]) > cutoff]

        removed = original_count - len(self.data["sessions"])
        if removed > 0:
            self._save_data()
            logger.info(f"Cleaned up {removed} old sessions (older than {days_to_keep} days)")

        return removed
