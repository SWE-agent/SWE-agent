"""GitHub integration state management.

This module provides persistent state management for GitHub integration,
supporting both Action and Bot modes while maintaining thread safety
and cost tracking.
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("swea-gh-state")


class GitHubState:
    """Manages persistent state for GitHub integration.

    Provides thread-safe state storage using SQLite, supporting:
    - Model state persistence
    - Event tracking and deduplication
    - Cost tracking and optimization
    - Concurrent access handling

    Args:
        db_path: Path to SQLite database file
        target_hourly_cost: Target cost in rupees per hour
    """

    def __init__(self, db_path: Path, target_hourly_cost: float = 10.0):
        """Initialize state manager."""
        self.db_path = db_path
        self.target_hourly_cost = target_hourly_cost
        self._conn = None
        self._lock = threading.Lock()

        # Initialize database
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local database connection.

        Returns:
            sqlite3.Connection: Database connection
        """
        if not self._conn:
            self._conn = sqlite3.connect(self.db_path)
            # Enable foreign keys
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._lock:
            conn = self._get_conn()
            conn.executescript("""
                -- Events table for tracking processed events
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    action TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    processed_at TIMESTAMP,
                    cost REAL,
                    tokens INTEGER
                );

                -- Model state table
                CREATE TABLE IF NOT EXISTS model_states (
                    event_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES events(id)
                );

                -- Cost tracking table
                CREATE TABLE IF NOT EXISTS cost_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    cost REAL NOT NULL,
                    tokens INTEGER NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES events(id)
                );

                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_events_type_action
                ON events(type, action);

                CREATE INDEX IF NOT EXISTS idx_events_created
                ON events(created_at);

                CREATE INDEX IF NOT EXISTS idx_cost_tracking_timestamp
                ON cost_tracking(timestamp);
            """)
            conn.commit()

    def save_event(self, event_id: str, event_type: str, action: str, created_at: datetime) -> None:
        """Save new event.

        Args:
            event_id: Unique event identifier
            event_type: Event type (issue, pr, discussion)
            action: Event action (opened, edited, etc.)
            created_at: Event creation timestamp
        """
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """
                INSERT OR IGNORE INTO events
                (id, type, action, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (event_id, event_type, action, created_at),
            )
            conn.commit()

    def mark_event_processed(self, event_id: str, cost: float, tokens: int) -> None:
        """Mark event as processed with cost tracking.

        Args:
            event_id: Event identifier
            cost: Processing cost in rupees
            tokens: Number of tokens processed
        """
        now = datetime.utcnow()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """
                UPDATE events
                SET processed_at = ?, cost = ?, tokens = ?
                WHERE id = ?
                """,
                (now, cost, tokens, event_id),
            )
            conn.execute(
                """
                INSERT INTO cost_tracking
                (event_id, timestamp, cost, tokens)
                VALUES (?, ?, ?, ?)
                """,
                (event_id, now, cost, tokens),
            )
            conn.commit()

    def save_model_state(self, event_id: str, state: dict[str, Any]) -> None:
        """Save model state for event.

        Args:
            event_id: Event identifier
            state: Model state dictionary
        """
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """
                INSERT OR REPLACE INTO model_states
                (event_id, state, updated_at)
                VALUES (?, ?, ?)
                """,
                (event_id, json.dumps(state), datetime.utcnow()),
            )
            conn.commit()

    def get_model_state(self, event_id: str) -> dict[str, Any] | None:
        """Get model state for event.

        Args:
            event_id: Event identifier

        Returns:
            Optional[Dict]: Model state if found
        """
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                """
                SELECT state FROM model_states
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()

            if row:
                return json.loads(row[0])
            return None

    def get_hourly_cost(self, hours: int = 1) -> float:
        """Get average hourly cost for recent events.

        Args:
            hours: Number of hours to look back

        Returns:
            float: Average hourly cost in rupees
        """
        with self._lock:
            conn = self._get_conn()
            start_time = datetime.utcnow() - timedelta(hours=hours)
            row = conn.execute(
                """
                SELECT SUM(cost) / ? as hourly_cost
                FROM cost_tracking
                WHERE timestamp >= ?
                """,
                (hours, start_time),
            ).fetchone()

            return row[0] or 0.0

    def get_event_stats(self, event_type: str | None = None, hours: int = 24) -> list[tuple[str, int, float, int]]:
        """Get event processing statistics.

        Args:
            event_type: Optional event type filter
            hours: Number of hours to look back

        Returns:
            List[Tuple]: List of (type, count, total_cost, total_tokens)
        """
        with self._lock:
            conn = self._get_conn()
            start_time = datetime.utcnow() - timedelta(hours=hours)

            query = """
                SELECT type, COUNT(*) as count,
                       SUM(cost) as total_cost,
                       SUM(tokens) as total_tokens
                FROM events
                WHERE processed_at >= ?
            """
            params = [start_time]

            if event_type:
                query += " AND type = ?"
                params.append(event_type)

            query += " GROUP BY type"

            return conn.execute(query, params).fetchall()

    def is_cost_efficient(self) -> bool:
        """Check if current processing is within cost target.

        Returns:
            bool: True if hourly cost is below target
        """
        current_cost = self.get_hourly_cost()
        return current_cost <= self.target_hourly_cost

    def cleanup_old_events(self, days: int = 30) -> int:
        """Clean up old event data.

        Args:
            days: Age in days of data to remove

        Returns:
            int: Number of events cleaned up
        """
        with self._lock:
            conn = self._get_conn()
            cutoff = datetime.utcnow() - timedelta(days=days)

            # Start transaction
            conn.execute("BEGIN")
            try:
                # Delete old cost tracking entries
                conn.execute("DELETE FROM cost_tracking WHERE timestamp < ?", (cutoff,))

                # Delete old model states
                conn.execute(
                    """
                    DELETE FROM model_states
                    WHERE event_id IN (
                        SELECT id FROM events WHERE created_at < ?
                    )
                    """,
                    (cutoff,),
                )

                # Delete old events and get count
                cursor = conn.execute("DELETE FROM events WHERE created_at < ?", (cutoff,))
                deleted = cursor.rowcount

                conn.commit()
                return deleted
            except:
                conn.rollback()
                raise

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
