"""Tests for GitHub state management."""

import sqlite3
import threading
from datetime import datetime, timedelta

import pytest

from sweagent.github.state import GitHubState


@pytest.fixture
def db_path(tmp_path):
    """Create temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def state(db_path):
    """Create state manager."""
    return GitHubState(db_path)


def test_state_init(state, db_path):
    """Test state initialization."""
    assert state.db_path == db_path
    assert state.target_hourly_cost == 10.0

    # Verify tables were created
    conn = sqlite3.connect(db_path)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = {t[0] for t in tables}

    assert "events" in table_names
    assert "model_states" in table_names
    assert "cost_tracking" in table_names


def test_save_event(state):
    """Test saving event."""
    event_id = "test-123"
    event_type = "issues"
    action = "opened"
    created_at = datetime.utcnow()

    # Save event
    state.save_event(event_id, event_type, action, created_at)

    # Verify saved
    conn = state._get_conn()
    row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()

    assert row is not None
    assert row[1] == event_type
    assert row[2] == action


def test_mark_event_processed(state):
    """Test marking event as processed."""
    # Save event first
    event_id = "test-456"
    state.save_event(event_id, "pull_request", "opened", datetime.utcnow())

    # Mark processed
    cost = 5.0
    tokens = 1000
    state.mark_event_processed(event_id, cost, tokens)

    # Verify event updated
    conn = state._get_conn()
    row = conn.execute("SELECT processed_at, cost, tokens FROM events WHERE id = ?", (event_id,)).fetchone()

    assert row is not None
    assert row[1] == cost
    assert row[2] == tokens

    # Verify cost tracking
    row = conn.execute("SELECT cost, tokens FROM cost_tracking WHERE event_id = ?", (event_id,)).fetchone()

    assert row is not None
    assert row[0] == cost
    assert row[1] == tokens


def test_model_state(state):
    """Test model state save/get."""
    event_id = "test-789"
    test_state = {"key": "value"}

    # Save state
    state.save_model_state(event_id, test_state)

    # Get state
    retrieved = state.get_model_state(event_id)
    assert retrieved == test_state


def test_get_hourly_cost(state):
    """Test getting hourly cost."""
    # Add some cost entries
    event_id = "test-cost"
    state.save_event(event_id, "issues", "opened", datetime.utcnow())

    state.mark_event_processed(event_id, 5.0, 1000)
    state.mark_event_processed(event_id, 3.0, 500)

    # Get hourly cost
    cost = state.get_hourly_cost()
    assert cost == 8.0  # 5.0 + 3.0


def test_get_event_stats(state):
    """Test getting event statistics."""
    # Add some events
    now = datetime.utcnow()

    # Recent event
    state.save_event("recent-1", "issues", "opened", now)
    state.mark_event_processed("recent-1", 5.0, 1000)

    # Old event
    state.save_event("old-1", "issues", "opened", now - timedelta(days=2))
    state.mark_event_processed("old-1", 3.0, 500)

    # Get stats for last hour
    stats = state.get_event_stats(hours=1)
    assert len(stats) == 1
    assert stats[0][1] == 1  # Count
    assert stats[0][2] == 5.0  # Cost


def test_cleanup_old_events(state):
    """Test cleaning up old events."""
    now = datetime.utcnow()

    # Add old and new events
    state.save_event("old-1", "issues", "opened", now - timedelta(days=40))
    state.save_event("new-1", "issues", "opened", now)

    # Clean up events older than 30 days
    deleted = state.cleanup_old_events(days=30)
    assert deleted == 1

    # Verify only new event remains
    conn = state._get_conn()
    count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert count == 1


def test_thread_safety(state):
    """Test thread safety of state operations."""

    def worker():
        for i in range(10):
            event_id = f"thread-{threading.get_ident()}-{i}"
            state.save_event(event_id, "issues", "opened", datetime.utcnow())
            state.mark_event_processed(event_id, 1.0, 100)

    # Run multiple threads
    threads = []
    for _ in range(5):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)

    # Wait for completion
    for t in threads:
        t.join()

    # Verify all events were saved
    conn = state._get_conn()
    count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert count == 50  # 5 threads * 10 events


def test_is_cost_efficient(state):
    """Test cost efficiency check."""
    # Add events with total cost above target
    event_id = "cost-test"
    state.save_event(event_id, "issues", "opened", datetime.utcnow())
    state.mark_event_processed(event_id, 15.0, 2000)

    # Check efficiency
    assert not state.is_cost_efficient()
