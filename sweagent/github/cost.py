"""GitHub integration cost optimization.

This module provides cost optimization strategies for GitHub operations,
maintaining a target cost efficiency of 10 rupees per hour.
"""

import logging
from datetime import datetime, timedelta

from .state import GitHubState

logger = logging.getLogger("swea-gh-cost")


class GitHubCostOptimizer:
    """Optimizes costs for GitHub operations.

    Implements cost optimization strategies:
    1. Event batching
    2. Model state caching
    3. Rate limiting
    4. Cost tracking

    Args:
        state: GitHubState instance for persistence
        target_hourly_cost: Target cost in rupees per hour
        max_batch_size: Maximum events to batch
        cache_ttl: Cache TTL in seconds
    """

    def __init__(
        self, state: GitHubState, target_hourly_cost: float = 10.0, max_batch_size: int = 5, cache_ttl: int = 3600
    ):
        """Initialize cost optimizer."""
        self.state = state
        self.target_hourly_cost = target_hourly_cost
        self.max_batch_size = max_batch_size
        self.cache_ttl = cache_ttl

        # Runtime tracking
        self._current_batch: list[dict] = []
        self._processed_events: set[str] = set()
        self._last_process_time = datetime.utcnow()
        self._rate_limit_window = timedelta(hours=1)
        self._rate_limit_tokens = 100
        self._rate_limit_last_reset = datetime.utcnow()

    def should_process_event(self, event: dict) -> bool:
        """Determine if event should be processed based on cost.

        Args:
            event: GitHub event payload

        Returns:
            bool: True if event should be processed
        """
        # Check if already processed
        event_id = self._get_event_id(event)
        if event_id in self._processed_events:
            logger.debug(f"Event {event_id} already processed")
            return False

        # Check cost efficiency
        if not self.state.is_cost_efficient():
            logger.warning("Cost efficiency target exceeded")
            return False

        # Check rate limits
        if not self._check_rate_limit():
            logger.warning("Rate limit exceeded")
            return False

        return True

    def add_to_batch(self, event: dict) -> bool:
        """Add event to current batch.

        Args:
            event: GitHub event payload

        Returns:
            bool: True if batch is ready for processing
        """
        event_id = self._get_event_id(event)
        if len(self._current_batch) < self.max_batch_size:
            self._current_batch.append(event)
            self._processed_events.add(event_id)
            return False

        return True

    def get_batch(self) -> list[dict]:
        """Get current batch of events.

        Returns:
            List[Dict]: Current batch
        """
        batch = self._current_batch
        self._current_batch = []
        return batch

    def track_processing(self, event_ids: list[str], cost: float, tokens: int) -> None:
        """Track event processing costs.

        Args:
            event_ids: List of processed event IDs
            cost: Total cost in rupees
            tokens: Total tokens processed
        """
        # Calculate per-event metrics
        event_count = len(event_ids)
        cost_per_event = cost / event_count
        tokens_per_event = tokens // event_count

        # Track each event
        for event_id in event_ids:
            self.state.mark_event_processed(event_id, cost_per_event, tokens_per_event)

        # Update rate limit tokens
        self._rate_limit_tokens -= event_count

    def get_cached_state(self, event_id: str) -> dict | None:
        """Get cached model state for event.

        Args:
            event_id: Event identifier

        Returns:
            Optional[Dict]: Cached state if found and valid
        """
        state = self.state.get_model_state(event_id)
        if not state:
            return None

        # Check TTL
        updated_at = datetime.fromisoformat(state.get("_updated_at", ""))
        if datetime.utcnow() - updated_at > timedelta(seconds=self.cache_ttl):
            return None

        return state

    def cache_state(self, event_id: str, state: dict) -> None:
        """Cache model state for event.

        Args:
            event_id: Event identifier
            state: Model state to cache
        """
        state["_updated_at"] = datetime.utcnow().isoformat()
        self.state.save_model_state(event_id, state)

    def _get_event_id(self, event: dict) -> str:
        """Get unique identifier for event.

        Args:
            event: GitHub event payload

        Returns:
            str: Event identifier
        """
        event_type = event.get("event_name", "unknown")
        if "issue" in event:
            return f"{event_type}-{event['issue']['number']}"
        elif "pull_request" in event:
            return f"{event_type}-{event['pull_request']['number']}"
        elif "discussion" in event:
            return f"{event_type}-{event['discussion']['number']}"
        return f"{event_type}-{hash(str(event))}"

    def _check_rate_limit(self) -> bool:
        """Check if within rate limits.

        Returns:
            bool: True if within limits
        """
        now = datetime.utcnow()

        # Reset window if needed
        if now - self._rate_limit_last_reset >= self._rate_limit_window:
            self._rate_limit_tokens = 100
            self._rate_limit_last_reset = now

        return self._rate_limit_tokens > 0

    def get_stats(self) -> tuple[float, int, float]:
        """Get processing statistics.

        Returns:
            Tuple[float, int, float]: (hourly_cost, events_processed, efficiency)
        """
        hourly_cost = self.state.get_hourly_cost()
        stats = self.state.get_event_stats(hours=1)

        total_events = sum(stat[1] for stat in stats)
        efficiency = self.target_hourly_cost / hourly_cost if hourly_cost > 0 else 1.0

        return hourly_cost, total_events, efficiency
