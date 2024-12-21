"""Tests for GitHub Action integration."""

import json
from unittest.mock import MagicMock

import pytest

from sweagent.agent.agents import Agent
from sweagent.github.action import GitHubActionRouter, UnsupportedEventError


@pytest.fixture
def mock_agent():
    """Create mock agent."""
    return MagicMock(spec=Agent)


@pytest.fixture
def event_path(tmp_path):
    """Create temporary event file."""
    return tmp_path / "event.json"


@pytest.fixture
def action_router(mock_agent, event_path):
    """Create action router with mock agent."""
    return GitHubActionRouter(agent=mock_agent, event_path=event_path, token="test-token")


def test_action_router_init(action_router):
    """Test router initialization."""
    assert action_router.agent is not None
    assert action_router.event_path is not None
    assert action_router.event is None
    assert action_router.hook is not None


def test_load_invalid_event(action_router):
    """Test loading invalid event file."""
    with pytest.raises(FileNotFoundError):
        action_router._load_event()


def test_load_invalid_json(action_router, event_path):
    """Test loading invalid JSON."""
    event_path.write_text("invalid json")
    with pytest.raises(json.JSONDecodeError):
        action_router._load_event()


def test_validate_unsupported_event(action_router):
    """Test validating unsupported event."""
    event = {"event_name": "unsupported"}
    with pytest.raises(UnsupportedEventError):
        action_router._validate_event(event)


def test_validate_unsupported_action(action_router):
    """Test validating unsupported action."""
    event = {"event_name": "issues", "action": "unsupported"}
    with pytest.raises(UnsupportedEventError):
        action_router._validate_event(event)


def test_handle_issue_event(action_router, event_path):
    """Test handling issue event."""
    event = {"event_name": "issues", "action": "opened", "issue": {"number": 123, "title": "Test Issue"}}
    event_path.write_text(json.dumps(event))

    # Handle event
    action_router.handle_event()

    # Verify agent was run
    action_router.agent.run.assert_called_once()


def test_handle_pr_event(action_router, event_path):
    """Test handling pull request event."""
    event = {"event_name": "pull_request", "action": "opened", "pull_request": {"number": 456, "title": "Test PR"}}
    event_path.write_text(json.dumps(event))

    # Handle event
    action_router.handle_event()

    # Verify agent was run
    action_router.agent.run.assert_called_once()


def test_handle_discussion_event(action_router, event_path):
    """Test handling discussion event."""
    event = {"event_name": "discussion", "action": "created", "discussion": {"number": 789, "title": "Test Discussion"}}
    event_path.write_text(json.dumps(event))

    # Handle event
    action_router.handle_event()

    # Verify agent was run
    action_router.agent.run.assert_called_once()
