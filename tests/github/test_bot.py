"""Tests for GitHub bot integration."""

import json
from http.client import HTTPConnection
from unittest.mock import MagicMock

import pytest

from sweagent.agent.agents import Agent
from sweagent.github.bot import GitHubBotRouter


@pytest.fixture
def mock_agent():
    """Create mock agent."""
    return MagicMock(spec=Agent)


@pytest.fixture
def bot_router(mock_agent):
    """Create bot router with mock agent."""
    return GitHubBotRouter(agent=mock_agent, webhook_port=8000, webhook_secret="test-secret", token="test-token")


def test_bot_router_init(bot_router):
    """Test router initialization."""
    assert bot_router.agent is not None
    assert bot_router.webhook_port == 8000
    assert bot_router.webhook_secret == "test-secret"
    assert bot_router.server is None
    assert bot_router.hook is not None


def test_validate_unsupported_event(bot_router):
    """Test validating unsupported event."""
    event = {"event_name": "unsupported"}
    with pytest.raises(Exception):
        bot_router._validate_event(event)


def test_validate_unsupported_action(bot_router):
    """Test validating unsupported action."""
    event = {"event_name": "issues", "action": "unsupported"}
    with pytest.raises(Exception):
        bot_router._validate_event(event)


def test_handle_issue_event(bot_router):
    """Test handling issue event."""
    event = {"event_name": "issues", "action": "opened", "issue": {"number": 123, "title": "Test Issue"}}

    # Handle event
    bot_router.handle_event(event)

    # Verify agent was run
    bot_router.agent.run.assert_called_once()


def test_handle_pr_event(bot_router):
    """Test handling pull request event."""
    event = {"event_name": "pull_request", "action": "opened", "pull_request": {"number": 456, "title": "Test PR"}}

    # Handle event
    bot_router.handle_event(event)

    # Verify agent was run
    bot_router.agent.run.assert_called_once()


def test_handle_discussion_event(bot_router):
    """Test handling discussion event."""
    event = {"event_name": "discussion", "action": "created", "discussion": {"number": 789, "title": "Test Discussion"}}

    # Handle event
    bot_router.handle_event(event)

    # Verify agent was run
    bot_router.agent.run.assert_called_once()


def test_webhook_server(bot_router):
    """Test webhook server start/stop."""
    # Start server
    bot_router.start()
    assert bot_router.server is not None

    # Stop server
    bot_router.stop()
    assert bot_router.server is None


def test_webhook_invalid_signature():
    """Test webhook with invalid signature."""
    router = GitHubBotRouter(agent=MagicMock(), webhook_port=8001, webhook_secret="test-secret", token="test-token")
    router.start()

    try:
        # Send request with invalid signature
        conn = HTTPConnection("localhost", 8001)
        headers = {"Content-Type": "application/json", "X-Hub-Signature-256": "invalid", "X-GitHub-Event": "issues"}
        conn.request("POST", "/", "{}", headers)
        response = conn.getresponse()

        # Verify unauthorized response
        assert response.status == 401
    finally:
        router.stop()


def test_webhook_valid_request():
    """Test webhook with valid request."""
    router = GitHubBotRouter(agent=MagicMock(), webhook_port=8002, webhook_secret="test-secret", token="test-token")
    router.start()

    try:
        # Create valid payload and signature
        payload = json.dumps(
            {"event_name": "issues", "action": "opened", "issue": {"number": 123, "title": "Test"}}
        ).encode()

        import hashlib
        import hmac

        signature = "sha256=" + hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()

        # Send request
        conn = HTTPConnection("localhost", 8002)
        headers = {"Content-Type": "application/json", "X-Hub-Signature-256": signature, "X-GitHub-Event": "issues"}
        conn.request("POST", "/", payload, headers)
        response = conn.getresponse()

        # Verify success response
        assert response.status == 200
    finally:
        router.stop()
