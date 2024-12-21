"""GitHub event hook for SWE-agent.

This module provides GitHub integration support for both Action and bot modes,
with built-in cost tracking and event handling capabilities.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ghapi.all import GhApi
from pydantic import BaseModel

from sweagent.agent.hooks.abstract import AbstractAgentHook
from sweagent.types import AgentInfo, StepOutput, Trajectory

if TYPE_CHECKING:
    from sweagent.agent.agents import Agent


class GitHubEventStats(BaseModel):
    """Statistics for GitHub event processing"""

    event_count: int = 0
    total_cost: float = 0.0
    last_event_time: datetime | None = None
    hourly_cost_rate: float = 0.0

    def update_stats(self, cost: float) -> None:
        """Update statistics with new event cost"""
        now = datetime.now()
        self.event_count += 1
        self.total_cost += cost

        if self.last_event_time:
            # Calculate hourly rate based on time difference
            hours = (now - self.last_event_time).total_seconds() / 3600
            if hours > 0:
                self.hourly_cost_rate = self.total_cost / hours

        self.last_event_time = now


class GitHubEventHook(AbstractAgentHook):
    """Hook for handling GitHub events in both Action and bot modes.

    Provides:
    - Cost tracking for model queries
    - Support for both Action and bot modes
    - GitHub API integration via GhApi
    - Event statistics tracking

    Args:
        token: GitHub API token
        mode: Operating mode ('action' or 'bot')
        target_hourly_cost: Target cost per hour in rupees (default: 10.0)
    """

    def __init__(self, token: str, mode: str = "action", target_hourly_cost: float = 10.0):
        """Initialize the GitHub event hook"""
        super().__init__()
        self.api = GhApi(token=token)
        self.mode = mode
        self.target_hourly_cost = target_hourly_cost
        self.stats = GitHubEventStats()
        self._current_event: dict[str, Any] | None = None
        self.logger = logging.getLogger("swea-gh")

    def on_init(self, *, agent: "Agent") -> None:
        """Called when agent is initialized.

        Args:
            agent: The agent instance
        """
        self.agent = agent

    def on_run_start(self) -> None:
        """Called when agent run starts"""
        if self._current_event:
            self.logger.info(f"Processing GitHub event: {self._current_event.get('action', 'unknown')}")

    def on_step_start(self) -> None:
        """Called when step starts"""
        pass

    def on_model_query(self, *, messages: list[dict[str, str]], agent: str) -> None:
        """Track costs for GitHub events.

        Updates statistics and checks against target hourly cost rate.
        Raises warning if cost rate exceeds target.

        Args:
            messages: List of message dictionaries
            agent: Agent name
        """
        # Estimate cost based on token count (simplified for now)
        total_tokens = sum(len(m["content"].split()) for m in messages)
        estimated_cost = total_tokens * 0.001  # Simplified cost estimation

        self.stats.update_stats(estimated_cost)

        if self.stats.hourly_cost_rate > self.target_hourly_cost:
            self.logger.warning(
                f"Cost rate ({self.stats.hourly_cost_rate:.2f} rupees/hour) "
                f"exceeds target ({self.target_hourly_cost:.2f} rupees/hour)"
            )

    def on_actions_generated(self, *, step: StepOutput) -> None:
        """Called when actions are generated"""
        pass

    def on_action_started(self, *, step: StepOutput) -> None:
        """Called when action execution starts"""
        pass

    def on_action_executed(self, *, step: StepOutput) -> None:
        """Called when action execution completes"""
        pass

    def on_step_done(self, *, step: StepOutput, info: AgentInfo) -> None:
        """Called when step is completed"""
        pass

    def on_run_done(self, *, trajectory: Trajectory, info: AgentInfo) -> None:
        """Called when agent run completes.

        Logs final statistics for the GitHub event processing.
        """
        self.logger.info(
            f"GitHub event processing complete. "
            f"Events: {self.stats.event_count}, "
            f"Total cost: {self.stats.total_cost:.2f} rupees, "
            f"Rate: {self.stats.hourly_cost_rate:.2f} rupees/hour"
        )

    def on_query_message_added(
        self,
        *,
        agent: str,
        role: str,
        content: str,
        message_type: str,
        is_demo: bool = False,
        thought: str = "",
        action: str = "",
        tool_calls: list[dict[str, str]] | None = None,
        tool_call_ids: list[str] | None = None,
    ) -> None:
        """Called when a message is added to the query history.

        Args:
            agent: Agent name
            role: Message role
            content: Message content
            message_type: Type of message
            is_demo: Whether this is a demo message
            thought: Thought content
            action: Action content
            tool_calls: Tool calls if any
            tool_call_ids: Tool call IDs if any
        """
        pass

    def on_tools_installation_started(self) -> None:
        """Called when tools installation starts"""
        pass

    def set_current_event(self, event: dict[str, Any]) -> None:
        """Set the current GitHub event being processed.

        Args:
            event: GitHub event payload
        """
        self._current_event = event
        self.logger.info(f"Set current GitHub event: {event.get('action', 'unknown')}")
