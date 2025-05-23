import os
from unittest import mock

import pytest

from sweagent.run.hooks.open_pr_gitlab import (
    OpenMRConfig,
    OpenMRHook,
)
from sweagent.types import AgentRunResult


@mock.patch.dict(os.environ, {"GITLAB_TOKEN": "test_token", "GITLAB_TOKEN_TYPE": "oauth2"})
class TestOpenMRHookWithGitlab:
    """Test OpenMRHook with GitLab issues"""

    @pytest.fixture
    def agent_run_result(self):
        """Fixture for AgentRunResult"""
        return AgentRunResult(
            info={
                "submission": "test_submission",
                "exit_status": "submitted",
            },
            trajectory=[],
        )

    @mock.patch("sweagent.utils.gitlab._get_project_id", return_value="123")
    @mock.patch("sweagent.utils.gitlab._get_gitlab_api_client")
    @mock.patch(
        "sweagent.utils.gitlab._parse_gitlab_issue_url",
        return_value=("https://gitlab.com", "jpaodev", "test-repo", "1"),
    )
    @mock.patch("sweagent.utils.gitlab._is_gitlab_issue_url", return_value=True)
    def test_should_open_mr_gitlab_open_issue(
        self, mock_is_issue, mock_parse_url, mock_api_client, mock_project_id, agent_run_result
    ):
        """Test should_open_mr with open GitLab issue"""
        # Create a hook with a mock problem statement
        hook = OpenMRHook(config=OpenMRConfig(skip_if_commits_reference_issue=True))
        hook._gitlab_token = "test_token"
        hook._gitlab_token_type = "oauth2"
        hook._problem_statement = mock.Mock()
        hook._problem_statement.gitlab_url = "https://gitlab.com/jpaodev/test-repo/-/issues/1"

        # Mock the GitLab API client
        mock_client = {"get": mock.Mock()}

        # Set up different responses for different API calls
        def get_side_effect(*args, **kwargs):
            # For issue data
            if args[0].endswith("/issues/1"):
                return {
                    "iid": 1,
                    "title": "Test Issue",
                    "description": "Test Description",
                    "state": "opened",  # Open state
                    "assignee": None,
                    "discussion_locked": False,
                }
            # For merge requests search
            elif "/merge_requests" in args[0]:
                return []  # No merge requests that mention the issue
            # Default empty response
            return []

        mock_client["get"].side_effect = get_side_effect
        mock_api_client.return_value = mock_client

        # Test should_open_mr - should succeed with open issue
        result = hook.should_open_mr(agent_run_result)
        assert result, "should_open_mr should return True for open issue"

    @mock.patch("sweagent.utils.gitlab._get_project_id", return_value="123")
    @mock.patch("sweagent.utils.gitlab._get_gitlab_api_client")
    @mock.patch(
        "sweagent.utils.gitlab._parse_gitlab_issue_url",
        return_value=("https://gitlab.com", "jpaodev", "test-repo", "1"),
    )
    @mock.patch("sweagent.utils.gitlab._is_gitlab_issue_url", return_value=True)
    def test_should_open_mr_gitlab_closed_issue(
        self, mock_is_issue, mock_parse_url, mock_api_client, mock_project_id, agent_run_result
    ):
        """Test should_open_mr with closed GitLab issue"""
        # Create a hook with a mock problem statement
        hook = OpenMRHook(config=OpenMRConfig(skip_if_commits_reference_issue=True))
        hook._gitlab_token = "test_token"
        hook._gitlab_token_type = "oauth2"
        hook._problem_statement = mock.Mock()
        hook._problem_statement.gitlab_url = "https://gitlab.com/jpaodev/test-repo/-/issues/1"

        # Mock the GitLab API client
        mock_client = {"get": mock.Mock()}

        # Set up different responses for different API calls
        def get_side_effect(*args, **kwargs):
            # For issue data
            if args[0].endswith("/issues/1"):
                return {
                    "iid": 1,
                    "title": "Test Issue",
                    "description": "Test Description",
                    "state": "closed",  # Closed state
                    "assignee": None,
                    "discussion_locked": False,
                }
            # For merge requests search
            elif "/merge_requests" in args[0]:
                return []  # No merge requests that mention the issue
            # Default empty response
            return []

        mock_client["get"].side_effect = get_side_effect
        mock_api_client.return_value = mock_client

        # Test should_open_mr - should fail for closed issue
        result = hook.should_open_mr(agent_run_result)
        assert not result, "should_open_mr should return False for closed issue"
