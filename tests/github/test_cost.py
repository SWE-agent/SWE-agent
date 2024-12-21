"""Tests for GitHub cost optimization."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from sweagent.github.cost import GitHubCostOptimizer
from sweagent.github.state import GitHubState


@pytest.fixture
def mock_state():
    """Create mock state manager."""
    state = MagicMock(spec=GitHubState)
    state.is_cost_efficient.return_value = True
    return state


@pytest.fixture
def optimizer(mock_state):
    """Create cost optimizer."""
    return GitHubCostOptimizer(state=mock_state, target_hourly_cost=10.0, max_batch_size=2)


def test_optimizer_init(optimizer):
    """Test optimizer initialization."""
    assert optimizer.target_hourly_cost == 10.0
    assert optimizer.max_batch_size == 2
    assert len(optimizer._current_batch) == 0
    assert len(optimizer._processed_events) == 0


def test_should_process_event(optimizer):
    """Test event processing decision."""
    event = {"event_name": "issues", "issue": {"number": 123}}

    # First time should be allowed
    assert optimizer.should_process_event(event)

    # Add to batch
    optimizer.add_to_batch(event)

    # Second time should be denied
    assert not optimizer.should_process_event(event)


def test_cost_efficiency_check(optimizer, mock_state):
    """Test cost efficiency check."""
    event = {"event_name": "issues", "issue": {"number": 123}}

    # Allow when efficient
    mock_state.is_cost_efficient.return_value = True
    assert optimizer.should_process_event(event)

    # Deny when inefficient
    mock_state.is_cost_efficient.return_value = False
    assert not optimizer.should_process_event(event)


def test_batch_processing(optimizer):
    """Test event batching."""
    events = [{"event_name": "issues", "issue": {"number": i}} for i in range(3)]

    # First event
    assert optimizer.should_process_event(events[0])
    assert not optimizer.add_to_batch(events[0])

    # Second event (completes batch)
    assert optimizer.should_process_event(events[1])
    assert optimizer.add_to_batch(events[1])

    # Get batch
    batch = optimizer.get_batch()
    assert len(batch) == 2
    assert batch[0]["issue"]["number"] == 0
    assert batch[1]["issue"]["number"] == 1


def test_cost_tracking(optimizer):
    """Test cost tracking."""
    event_ids = ["test-1", "test-2"]
    cost = 10.0
    tokens = 2000

    optimizer.track_processing(event_ids, cost, tokens)

    # Verify state updates
    calls = optimizer.state.mark_event_processed.call_args_list
    assert len(calls) == 2
    for call in calls:
        assert call[0][1] == 5.0  # Cost per event
        assert call[0][2] == 1000  # Tokens per event


def test_state_caching(optimizer):
    """Test model state caching."""
    event_id = "test-123"

    # Cache miss
    optimizer.state.get_model_state.return_value = None
    assert optimizer.get_cached_state(event_id) is None

    # Cache hit but expired
    old_state = {"key": "value", "_updated_at": (datetime.utcnow() - timedelta(seconds=3601)).isoformat()}
    optimizer.state.get_model_state.return_value = old_state
    assert optimizer.get_cached_state(event_id) is None

    # Cache hit and valid
    current_state = {"key": "value", "_updated_at": datetime.utcnow().isoformat()}
    optimizer.state.get_model_state.return_value = current_state
    assert optimizer.get_cached_state(event_id) is not None


def test_rate_limiting(optimizer):
    """Test rate limiting."""
    event = {"event_name": "issues", "issue": {"number": 123}}

    # Use up rate limit
    optimizer._rate_limit_tokens = 0
    assert not optimizer.should_process_event(event)

    # Reset window
    optimizer._rate_limit_last_reset = datetime.utcnow() - timedelta(hours=2)
    assert optimizer.should_process_event(event)
    assert optimizer._rate_limit_tokens == 100


def test_get_stats(optimizer):
    """Test getting statistics."""
    # Mock state responses
    optimizer.state.get_hourly_cost.return_value = 5.0
    optimizer.state.get_event_stats.return_value = [("issues", 10, 5.0, 1000)]

    # Get stats
    hourly_cost, events, efficiency = optimizer.get_stats()
    assert hourly_cost == 5.0
    assert events == 10
    assert efficiency == 2.0  # 10.0 target / 5.0 actual
