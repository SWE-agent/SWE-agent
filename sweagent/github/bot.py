"""GitHub bot integration for SWE-agent.

This module provides the router for handling GitHub bot events through webhooks,
supporting both issue and pull request events.
"""

import hashlib
import hmac
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from sweagent.agent.agents import Agent
from sweagent.agent.hooks.github import GitHubEventHook

logger = logging.getLogger("swea-gh-bot")


class UnsupportedEventError(Exception):
    """Raised when an unsupported event type is received."""

    pass


class GitHubWebhookHandler(BaseHTTPRequestHandler):
    """Handles GitHub webhook requests.

    Attributes:
        router: Reference to parent GitHubBotRouter
        secret: Webhook secret for signature verification
    """

    def __init__(self, *args, router: "GitHubBotRouter", secret: str, **kwargs):
        self.router = router
        self.secret = secret.encode()
        super().__init__(*args, **kwargs)

    def _verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature.

        Args:
            payload: Raw request payload
            signature: GitHub signature header

        Returns:
            bool: True if signature is valid
        """
        if not signature.startswith("sha256="):
            return False

        expected = hmac.new(self.secret, payload, hashlib.sha256).hexdigest()
        received = signature.replace("sha256=", "")
        return hmac.compare_digest(expected, received)

    def do_POST(self):
        """Handle POST requests from GitHub webhooks."""
        # Read and verify payload
        content_length = int(self.headers["Content-Length"])
        payload = self.rfile.read(content_length)

        # Verify signature
        signature = self.headers.get("X-Hub-Signature-256", "")
        if not self._verify_signature(payload, signature):
            self.send_response(401)
            self.end_headers()
            return

        # Parse event
        try:
            event = json.loads(payload)
            event_type = self.headers.get("X-GitHub-Event", "")
            if not event_type:
                error_msg = "Missing X-GitHub-Event header"
                raise ValueError(error_msg)

            # Add event type to payload
            event["event_name"] = event_type

            # Route event
            self.router.handle_event(event)
            self.send_response(200)
            self.end_headers()

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid webhook payload: {e}")
            self.send_response(400)
            self.end_headers()
        except UnsupportedEventError as e:
            logger.warning(f"Unsupported event: {e}")
            self.send_response(422)
            self.end_headers()
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            self.send_response(500)
            self.end_headers()


class GitHubBotRouter:
    """Routes GitHub bot events to appropriate handlers.

    Supports:
    - Issue events
    - Pull request events
    - Discussion events

    Args:
        agent: The SWE agent instance
        webhook_port: Port to listen for webhooks
        webhook_secret: Secret for webhook signature verification
        token: GitHub API token
    """

    SUPPORTED_EVENTS = {
        "issues": ["opened", "edited"],
        "pull_request": ["opened", "synchronize"],
        "discussion": ["created", "edited"],
    }

    def __init__(
        self,
        agent: Agent,
        webhook_port: int = 8000,
        webhook_secret: str = "",
        token: str = "",
    ):
        """Initialize the GitHub bot router."""
        self.agent = agent
        self.webhook_port = webhook_port
        self.webhook_secret = webhook_secret
        self.server: HTTPServer | None = None
        self._server_thread: threading.Thread | None = None

        # Initialize GitHub hook
        self.hook = GitHubEventHook(token=token, mode="bot")
        self.agent.hooks.add_hook(self.hook)

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
        self.hook.set_current_event(event)
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

    def handle_event(self, event: dict[str, Any]) -> None:
        """Route GitHub event to appropriate handler.

        Args:
            event: GitHub event payload

        Raises:
            UnsupportedEventError: If event type not supported
        """
        # Validate event
        self._validate_event(event)

        # Route to appropriate handler
        event_name = event["event_name"]
        handlers = {
            "issues": self._handle_issue,
            "pull_request": self._handle_pull_request,
            "discussion": self._handle_discussion,
        }

        handler = handlers[event_name]
        handler(event)

    def start(self) -> None:
        """Start the webhook server.

        Raises:
            RuntimeError: If server is already running
        """
        if self.server:
            error_msg = "Webhook server is already running"
            raise RuntimeError(error_msg)

        def create_handler(*args, **kwargs):
            return GitHubWebhookHandler(*args, router=self, secret=self.webhook_secret, **kwargs)

        self.server = HTTPServer(("", self.webhook_port), create_handler)
        logger.info(f"Starting webhook server on port {self.webhook_port}")

        # Run server in background thread
        self._server_thread = threading.Thread(target=self.server.serve_forever)
        self._server_thread.daemon = True
        self._server_thread.start()

    def stop(self) -> None:
        """Stop the webhook server."""
        if self.server:
            logger.info("Stopping webhook server")
            self.server.shutdown()
            self.server.server_close()
            self._server_thread = None
            self.server = None
