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
                now = datetime.utcnow()
                session["ended_at"] = now.isoformat()
                
                # Calculate current duration
                try:
                    started = datetime.fromisoformat(session["started_at"])
                    duration = (now - started).total_seconds() / 60  # minutes
                    session["duration_minutes"] = round(duration, 2)
                except Exception as e:
                    logger.error(f"Failed to calculate session duration: {e}")

                # Update aggregations in real-time
                self._update_user_stats(session)
                self._update_daily_stats(session)
                
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
        """Update aggregated user statistics - recalculates from all sessions"""
        discord_id = session["discord_id"]

        # Get all sessions for this user
        user_sessions = [s for s in self.data["sessions"] if s["discord_id"] == discord_id]
        
        if not user_sessions:
            return
        
        # Get unique session IDs (to count unique sessions, not updates)
        unique_session_ids = set(s["session_id"] for s in user_sessions)
        
        # Calculate stats from ALL user sessions
        total_time = sum(s.get("duration_minutes", 0) for s in user_sessions)
        total_sessions = len(unique_session_ids)
        
        # Get all unique devices
        device_history = list(set(s["device_info"] for s in user_sessions if s.get("device_info")))
        
        # Get first and last seen
        sorted_sessions = sorted(user_sessions, key=lambda s: s["started_at"])
        first_seen = sorted_sessions[0]["started_at"]
        last_seen = sorted_sessions[-1].get("ended_at") or sorted_sessions[-1]["started_at"]

        # Update or create user stats
        self.data["user_stats"][discord_id] = {
            "username": session["username"],
            "first_seen": first_seen,
            "last_seen": last_seen,
            "total_sessions": total_sessions,
            "total_time_minutes": round(total_time, 2),
            "avg_session_duration": round(total_time / total_sessions, 2) if total_sessions > 0 else 0,
            "device_history": device_history,
        }

    def _update_daily_stats(self, session: Dict[str, Any]) -> None:
        """Update daily statistics - recalculates from all sessions for the day"""
        try:
            date = datetime.fromisoformat(session["started_at"]).date().isoformat()
        except Exception:
            date = datetime.utcnow().date().isoformat()

        # Get all sessions for this date
        sessions_for_date = [
            s for s in self.data["sessions"]
            if datetime.fromisoformat(s["started_at"]).date().isoformat() == date
        ]
        
        if not sessions_for_date:
            return
        
        # Calculate stats from ALL sessions on this date
        unique_users = list(set(s["discord_id"] for s in sessions_for_date))
        unique_session_ids = set(s["session_id"] for s in sessions_for_date)
        total_sessions = len(unique_session_ids)
        total_actions = sum(s.get("actions_count", 0) for s in sessions_for_date)
        total_duration = sum(s.get("duration_minutes", 0) for s in sessions_for_date)
        
        # Update daily stats
        self.data["daily_stats"][date] = {
            "unique_users": unique_users,
            "total_sessions": total_sessions,
            "total_actions": total_actions,
            "total_duration_minutes": round(total_duration, 2),
            "avg_session_duration": round(total_duration / total_sessions, 2) if total_sessions > 0 else 0,
        }

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

    def reprocess_all_sessions(self) -> Dict[str, int]:
        """Reprocess all sessions to rebuild user_stats and daily_stats from scratch"""
        logger.info("Reprocessing all sessions to rebuild aggregations...")
        
        # Clear existing aggregations
        self.data["user_stats"] = {}
        self.data["daily_stats"] = {}
        
        # Process each session
        processed = 0
        for session in self.data["sessions"]:
            # Ensure session has ended_at (use started_at as fallback)
            if not session.get("ended_at"):
                session["ended_at"] = session["started_at"]
            
            # Ensure duration is calculated
            if session.get("duration_minutes", 0) == 0:
                try:
                    started = datetime.fromisoformat(session["started_at"])
                    ended = datetime.fromisoformat(session["ended_at"])
                    duration = (ended - started).total_seconds() / 60
                    session["duration_minutes"] = round(duration, 2)
                except Exception:
                    session["duration_minutes"] = 0
            
            # Update aggregations
            try:
                self._update_user_stats(session)
                self._update_daily_stats(session)
                processed += 1
            except Exception as e:
                logger.error(f"Failed to process session {session.get('session_id')}: {e}")
        
        self._save_data()
        
        result = {
            "sessions_processed": processed,
            "total_users": len(self.data["user_stats"]),
            "total_days": len(self.data["daily_stats"]),
        }
        
        logger.info(f"Reprocessing complete: {result}")
        return result
