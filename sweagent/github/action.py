"""GitHub Action integration for SWE-agent.

This module provides the router for handling GitHub Action events,
supporting both issue and pull request events.
"""

import json
import logging
from pathlib import Path
from typing import Any

from sweagent.agent.agents import Agent
from sweagent.agent.hooks.github import GitHubEventHook

logger = logging.getLogger("swea-gh-action")


class UnsupportedEventError(Exception):
    """Raised when an unsupported event type is received."""

    pass


class GitHubActionRouter:
    """Routes GitHub Action events to appropriate handlers.

    Supports:
    - Issue events
    - Pull request events
    - Discussion events

    Args:
        agent: The SWE agent instance
        event_path: Path to GitHub event payload JSON
        token: GitHub API token
    """

    SUPPORTED_EVENTS = {
        "issues": ["opened", "edited"],
        "pull_request": ["opened", "synchronize"],
        "discussion": ["created", "edited"],
    }

    def __init__(self, agent: Agent, event_path: Path, token: str):
        """Initialize the GitHub Action router."""
        self.agent = agent
        self.event_path = event_path
        self.event: dict[str, Any] | None = None

        # Initialize GitHub hook
        self.hook = GitHubEventHook(token=token, mode="action")
        self.agent.hooks.add_hook(self.hook)

    def _load_event(self) -> dict[str, Any]:
        """Load GitHub event from event path.

        Returns:
            Dict containing the event payload

        Raises:
            FileNotFoundError: If event file doesn't exist
            json.JSONDecodeError: If event file is invalid JSON
        """
        try:
            with open(self.event_path) as f:
                event = json.load(f)
            logger.info(f"Loaded GitHub event from {self.event_path}")
            return event
        except FileNotFoundError:
            logger.error(f"Event file not found: {self.event_path}")
            raise
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in event file: {self.event_path}")
            raise

    def _validate_event(self, event: dict[str, Any]) -> None:
        """Validate that the event type and action are supported.

        Args:
            event: GitHub event payload

        Raises:
            UnsupportedEventError: If event type or action not supported
        """
        event_name = event.get("event_name")
        if event_name not in self.SUPPORTED_EVENTS:
            error_msg = f"Unsupported event type: {event_name}"
            raise UnsupportedEventError(error_msg)

        action = event.get("action")
        if action not in self.SUPPORTED_EVENTS[event_name]:
            error_msg = f"Unsupported action '{action}' for event type '{event_name}'"
            raise UnsupportedEventError(error_msg)

    def _handle_issue(self, event: dict[str, Any]) -> None:
        """Handle GitHub issue event.

        Args:
            event: Issue event payload
        """
        issue = event["issue"]
        logger.info(f"Processing issue #{issue['number']}: {issue['title']}")
        # Set event in hook for cost tracking
        self.hook.set_current_event(event)
        # Run agent on issue
        self.agent.run()

    def _handle_pull_request(self, event: dict[str, Any]) -> None:
        """Handle GitHub pull request event.

        Args:
            event: Pull request event payload
        """
        pr = event["pull_request"]
        logger.info(f"Processing PR #{pr['number']}: {pr['title']}")
        self.hook.set_current_event(event)
        self.agent.run()

    def _handle_discussion(self, event: dict[str, Any]) -> None:
        """Handle GitHub discussion event.

        Args:
            event: Discussion event payload
        """
        discussion = event["discussion"]
        logger.info(f"Processing discussion #{discussion['number']}: {discussion['title']}")
        self.hook.set_current_event(event)
        self.agent.run()

    def handle_event(self) -> None:
        """Route GitHub event to appropriate handler.

        Raises:
            UnsupportedEventError: If event type not supported
        """
        # Load and validate event
        self.event = self._load_event()
        self._validate_event(self.event)

        # Route to appropriate handler
        event_name = self.event["event_name"]
        handlers = {
            "issues": self._handle_issue,
            "pull_request": self._handle_pull_request,
            "discussion": self._handle_discussion,
        }

        handler = handlers[event_name]
        handler(self.event)
