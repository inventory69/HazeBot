"""
SQLite Database Module for Analytics
Provides high-performance analytics storage with proper indexing and querying.

Key Features:
- Connection pooling for thread-safety
- Automatic schema creation and migration
- Optimized indexes for common queries
- Transaction support for data consistency
- Backward compatible with JSON format
"""

import sqlite3
import json
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
from Utils.Logger import Logger as logger


class AnalyticsDatabase:
    """High-performance SQLite database for analytics data"""

    def __init__(self, db_path: Path):
        """
        Initialize analytics database

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._lock = threading.Lock()

        # Create tables if they don't exist
        self._initialize_database()

    @contextmanager
    def _get_connection(self):
        """Get thread-local database connection with automatic commit/rollback"""
        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30.0)
            self._local.connection.row_factory = sqlite3.Row  # Enable column access by name

            # Performance optimizations
            self._local.connection.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
            self._local.connection.execute("PRAGMA synchronous=NORMAL")  # Faster writes
            self._local.connection.execute("PRAGMA cache_size=-64000")  # 64MB cache
            self._local.connection.execute("PRAGMA temp_store=MEMORY")  # Temp tables in memory

        connection = self._local.connection
        try:
            yield connection
            connection.commit()
        except Exception as e:
            connection.rollback()
            raise e

    def _initialize_database(self):
        """Create database schema with optimized indexes"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if tables already exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
            tables_exist = cursor.fetchone() is not None

            # Sessions table - Core analytics data
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    discord_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    duration_minutes REAL DEFAULT 0,
                    platform TEXT,
                    device_info TEXT,
                    app_version TEXT,
                    ip_address TEXT,
                    actions_count INTEGER DEFAULT 0,
                    endpoints_used TEXT,  -- JSON: {"endpoint": count}
                    screens_visited TEXT,  -- JSON array
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)

            # User stats table - Aggregated per user
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_stats (
                    discord_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    total_sessions INTEGER DEFAULT 0,
                    total_duration_minutes REAL DEFAULT 0,
                    total_actions INTEGER DEFAULT 0,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    favorite_platform TEXT,
                    endpoints_accessed TEXT,  -- JSON: {"endpoint": count}
                    updated_at TEXT DEFAULT (datetime('now'))
                )
            """)

            # Daily stats table - Aggregated per day
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT PRIMARY KEY,
                    total_sessions INTEGER DEFAULT 0,
                    unique_users INTEGER DEFAULT 0,
                    total_actions INTEGER DEFAULT 0,
                    total_duration_minutes REAL DEFAULT 0,
                    avg_session_duration REAL DEFAULT 0,
                    new_users INTEGER DEFAULT 0,
                    platforms TEXT,  -- JSON: {"platform": count}
                    top_endpoints TEXT,  -- JSON: {"endpoint": count}
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)

            # Error logs table - Error tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS error_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signature TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    endpoint TEXT,
                    discord_id TEXT,
                    username TEXT,
                    occurred_at TEXT NOT NULL,
                    stack_trace TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)

            # Create optimized indexes
            indexes = [
                # Sessions indexes
                "CREATE INDEX IF NOT EXISTS idx_sessions_discord_id ON sessions(discord_id)",
                "CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON sessions(started_at)",
                "CREATE INDEX IF NOT EXISTS idx_sessions_ended_at ON sessions(ended_at)",
                "CREATE INDEX IF NOT EXISTS idx_sessions_platform ON sessions(platform)",
                # User stats indexes
                "CREATE INDEX IF NOT EXISTS idx_user_stats_username ON user_stats(username)",
                "CREATE INDEX IF NOT EXISTS idx_user_stats_last_seen ON user_stats(last_seen)",
                "CREATE INDEX IF NOT EXISTS idx_user_stats_total_sessions ON user_stats(total_sessions DESC)",
                # Daily stats indexes
                "CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date DESC)",
                # Error logs indexes
                "CREATE INDEX IF NOT EXISTS idx_error_logs_signature ON error_logs(signature)",
                "CREATE INDEX IF NOT EXISTS idx_error_logs_occurred_at ON error_logs(occurred_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_error_logs_endpoint ON error_logs(endpoint)",
                "CREATE INDEX IF NOT EXISTS idx_error_logs_discord_id ON error_logs(discord_id)",
            ]

            for index_sql in indexes:
                cursor.execute(index_sql)

            conn.commit()

            # Quiet - no logging needed for schema creation

    # ==================== Session Operations ====================

    def create_session(self, session_data: Dict[str, Any]) -> bool:
        """
        Create a new session

        Args:
            session_data: Session data dictionary

        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO sessions (
                        session_id, discord_id, username, started_at, ended_at,
                        duration_minutes, platform, device_info, app_version,
                        ip_address, actions_count, endpoints_used, screens_visited
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        session_data.get("session_id"),
                        session_data.get("discord_id"),
                        session_data.get("username"),
                        session_data.get("started_at"),
                        session_data.get("ended_at"),
                        session_data.get("duration_minutes", 0),
                        session_data.get("platform"),
                        session_data.get("device_info"),
                        session_data.get("app_version"),
                        session_data.get("ip_address"),
                        session_data.get("actions_count", 0),
                        json.dumps(session_data.get("endpoints_used", {})),
                        json.dumps(session_data.get("screens_visited", [])),
                    ),
                )

                return True
        except sqlite3.IntegrityError:
            logger.warning(f"Session {session_data.get('session_id')} already exists")
            return False
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return False

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing session

        Args:
            session_id: Session ID to update
            updates: Dictionary of fields to update

        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Build dynamic UPDATE query
                set_clauses = []
                values = []

                for key, value in updates.items():
                    if key in ("endpoints_used", "screens_visited"):
                        set_clauses.append(f"{key} = ?")
                        values.append(json.dumps(value))
                    else:
                        set_clauses.append(f"{key} = ?")
                        values.append(value)

                if not set_clauses:
                    return True

                values.append(session_id)
                query = f"UPDATE sessions SET {', '.join(set_clauses)} WHERE session_id = ?"

                cursor.execute(query, values)
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update session {session_id}: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
                row = cursor.fetchone()

                if row:
                    return self._row_to_dict(row)
                return None
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None

    def get_sessions(
        self,
        discord_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get sessions with optional filters

        Args:
            discord_id: Filter by user
            start_date: Filter by start date (ISO format)
            end_date: Filter by end date (ISO format)
            limit: Maximum number of results

        Returns:
            List of session dictionaries
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM sessions WHERE 1=1"
                params = []

                if discord_id:
                    query += " AND discord_id = ?"
                    params.append(discord_id)

                if start_date:
                    query += " AND started_at >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND started_at <= ?"
                    params.append(end_date)

                query += " ORDER BY started_at DESC"

                if limit:
                    query += " LIMIT ?"
                    params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get sessions: {e}")
            return []

    # ==================== User Stats Operations ====================

    def upsert_user_stats(self, user_data: Dict[str, Any]) -> bool:
        """Insert or update user stats"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO user_stats (
                        discord_id, username, total_sessions, total_duration_minutes,
                        total_actions, first_seen, last_seen, favorite_platform,
                        endpoints_accessed, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(discord_id) DO UPDATE SET
                        username = excluded.username,
                        total_sessions = excluded.total_sessions,
                        total_duration_minutes = excluded.total_duration_minutes,
                        total_actions = excluded.total_actions,
                        last_seen = excluded.last_seen,
                        favorite_platform = excluded.favorite_platform,
                        endpoints_accessed = excluded.endpoints_accessed,
                        updated_at = datetime('now')
                """,
                    (
                        user_data.get("discord_id"),
                        user_data.get("username"),
                        user_data.get("total_sessions", 0),
                        user_data.get("total_duration_minutes", 0),
                        user_data.get("total_actions", 0),
                        user_data.get("first_seen"),
                        user_data.get("last_seen"),
                        user_data.get("favorite_platform"),
                        json.dumps(user_data.get("endpoints_accessed", {})),
                    ),
                )

                return True
        except Exception as e:
            logger.error(f"Failed to upsert user stats: {e}")
            return False

    def get_user_stats(self, discord_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get user stats, optionally filtered by discord_id"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if discord_id:
                    cursor.execute("SELECT * FROM user_stats WHERE discord_id = ?", (discord_id,))
                else:
                    cursor.execute("SELECT * FROM user_stats ORDER BY total_sessions DESC")

                rows = cursor.fetchall()
                return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get user stats: {e}")
            return []

    # ==================== Daily Stats Operations ====================

    def upsert_daily_stats(self, date: str, stats_data: Dict[str, Any]) -> bool:
        """Insert or update daily stats"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO daily_stats (
                        date, total_sessions, unique_users, total_actions,
                        total_duration_minutes, avg_session_duration, new_users,
                        platforms, top_endpoints
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date) DO UPDATE SET
                        total_sessions = excluded.total_sessions,
                        unique_users = excluded.unique_users,
                        total_actions = excluded.total_actions,
                        total_duration_minutes = excluded.total_duration_minutes,
                        avg_session_duration = excluded.avg_session_duration,
                        new_users = excluded.new_users,
                        platforms = excluded.platforms,
                        top_endpoints = excluded.top_endpoints
                """,
                    (
                        date,
                        stats_data.get("total_sessions", 0),
                        stats_data.get("unique_users", 0),
                        stats_data.get("total_actions", 0),
                        stats_data.get("total_duration_minutes", 0),
                        stats_data.get("avg_session_duration", 0),
                        stats_data.get("new_users", 0),
                        json.dumps(stats_data.get("platforms", {})),
                        json.dumps(stats_data.get("top_endpoints", {})),
                    ),
                )

                return True
        except Exception as e:
            logger.error(f"Failed to upsert daily stats: {e}")
            return False

    def get_daily_stats(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get daily stats with optional date range"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM daily_stats WHERE 1=1"
                params = []

                if start_date:
                    query += " AND date >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND date <= ?"
                    params.append(end_date)

                query += " ORDER BY date DESC"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get daily stats: {e}")
            return []

    # ==================== Error Logs Operations ====================

    def create_error_log(self, error_data: Dict[str, Any]) -> bool:
        """Create error log entry"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO error_logs (
                        signature, error_type, message, endpoint, discord_id,
                        username, occurred_at, stack_trace
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        error_data.get("signature"),
                        error_data.get("error_type"),
                        error_data.get("message"),
                        error_data.get("endpoint"),
                        error_data.get("discord_id"),
                        error_data.get("username"),
                        error_data.get("occurred_at"),
                        error_data.get("stack_trace"),
                    ),
                )

                return True
        except Exception as e:
            logger.error(f"Failed to create error log: {e}")
            return False

    def get_error_logs(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        signature: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get error logs with filters"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM error_logs WHERE 1=1"
                params = []

                if start_date:
                    query += " AND occurred_at >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND occurred_at <= ?"
                    params.append(end_date)

                if signature:
                    query += " AND signature = ?"
                    params.append(signature)

                query += " ORDER BY occurred_at DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get error logs: {e}")
            return []

    # ==================== Utility Methods ====================

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert SQLite row to dictionary with JSON deserialization"""
        result = dict(row)

        # Deserialize JSON fields
        json_fields = ["endpoints_used", "screens_visited", "endpoints_accessed", "platforms", "top_endpoints"]
        for field in json_fields:
            if field in result and result[field]:
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    result[field] = {} if field != "screens_visited" else []

        return result

    def vacuum(self):
        """Optimize database (reclaim space, rebuild indexes)"""
        try:
            with self._get_connection() as conn:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
        except Exception as e:
            logger.error(f"Failed to optimize database: {e}")

    def get_database_size(self) -> int:
        """Get database file size in bytes"""
        try:
            return self.db_path.stat().st_size
        except Exception:
            return 0

    def reset_all_data(self) -> Dict[str, int]:
        """
        Delete ALL analytics data from all tables
        
        Returns:
            Dictionary with count of deleted rows per table
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Count rows before deletion
                cursor.execute("SELECT COUNT(*) FROM sessions")
                sessions_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM user_stats")
                users_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM daily_stats")
                daily_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM error_logs")
                errors_count = cursor.fetchone()[0]
                
                # Delete all data
                cursor.execute("DELETE FROM sessions")
                cursor.execute("DELETE FROM user_stats")
                cursor.execute("DELETE FROM daily_stats")
                cursor.execute("DELETE FROM error_logs")
                
                # Reset autoincrement counters
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='error_logs'")
                
                # Vacuum to reclaim space
                conn.commit()
                cursor.execute("VACUUM")
                
                logger.info(f"🗑️ Analytics reset: {sessions_count} sessions, {users_count} users, {daily_count} daily stats, {errors_count} errors deleted")
                
                return {
                    "sessions_deleted": sessions_count,
                    "users_deleted": users_count,
                    "daily_stats_deleted": daily_count,
                    "errors_deleted": errors_count
                }
        except Exception as e:
            logger.error(f"Failed to reset analytics data: {e}")
            raise

    def close(self):
        """Close database connection"""
        if hasattr(self._local, "connection"):
            self._local.connection.close()
            delattr(self._local, "connection")
