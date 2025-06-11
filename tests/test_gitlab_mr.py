import os
from collections.abc import Generator
from typing import Any
from unittest import mock
from unittest.mock import Mock, patch

import pytest

from sweagent.environment.swe_env import SWEEnv
from sweagent.run.hooks.open_pr_gitlab import (
    OpenMRConfig,
    OpenMRHook,
    open_mr,
)
from sweagent.types import AgentRunResult
from sweagent.utils.gitlab import InvalidGitlabURL


@pytest.fixture
def open_mr_hook() -> OpenMRHook:
    """Create an OpenMRHook instance for testing."""
    config = OpenMRConfig(skip_if_commits_reference_issue=True)
    hook = OpenMRHook(config)
    # Set up the hook with test values
    hook._gitlab_token = "test_token"  # nosec: B105
    hook._gitlab_token_type = "oauth2"  # nosec: B105
    hook._problem_statement = mock.Mock()
    hook._problem_statement.gitlab_url = "https://gitlab.com/jpaodev/test-repo/-/issues/1"
    return hook


@mock.patch.dict(os.environ, {"GITLAB_TOKEN": "test_token", "GITLAB_TOKEN_TYPE": "oauth2"})
class TestOpenMRHookWithGitlab:
    """Tests for OpenMRHook with GitLab integration."""

    @pytest.fixture
    def mock_problem_statement(self) -> Mock:
        ps = mock.Mock()
        ps.gitlab_url = "https://gitlab.com/jpaodev/test-repo/-/issues/1"
        return ps

    @pytest.fixture
    def agent_run_result(self) -> AgentRunResult:
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
        self,
        mock_is_issue: Mock,
        mock_parse_url: Mock,
        mock_api_client: Mock,
        mock_project_id: Mock,
        agent_run_result: AgentRunResult,
        open_mr_hook: OpenMRHook,
    ):
        """Test should_open_mr with open GitLab issue"""
        # Mock the GitLab API client
        mock_client = {"get": mock.Mock()}

        # Set up different responses for different API calls
        def get_side_effect(*args: str, **kwargs: dict[str, Any]) -> dict[str, Any] | list[Any]:
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
        result = open_mr_hook.should_open_mr(agent_run_result)
        assert result, "should_open_mr should return True for open issue"

    @mock.patch("sweagent.utils.gitlab._get_project_id", return_value="123")
    @mock.patch("sweagent.utils.gitlab._get_gitlab_api_client")
    @mock.patch(
        "sweagent.utils.gitlab._parse_gitlab_issue_url",
        return_value=("https://gitlab.com", "jpaodev", "test-repo", "1"),
    )
    @mock.patch("sweagent.utils.gitlab._is_gitlab_issue_url", return_value=True)
    def test_should_open_mr_gitlab_closed_issue(
        self,
        mock_is_issue: Mock,
        mock_parse_url: Mock,
        mock_api_client: Mock,
        mock_project_id: Mock,
        agent_run_result: AgentRunResult,
        open_mr_hook: OpenMRHook,
    ):
        """Test should_open_mr with closed GitLab issue"""
        # Mock the GitLab API client
        mock_client = {"get": mock.Mock()}

        # Set up different responses for different API calls
        def get_side_effect(*args: str, **kwargs: dict[str, Any]) -> dict[str, Any] | list[Any]:
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
        result = open_mr_hook.should_open_mr(agent_run_result)
        assert not result, "should_open_mr should return False for closed issue"

    def test_should_open_mr_no_submission(self, open_mr_hook: OpenMRHook, agent_run_result: AgentRunResult):
        """Test should_open_mr when there is no submission."""
        agent_run_result.info["submission"] = None
        result = open_mr_hook.should_open_mr(agent_run_result)
        assert not result, "should_open_mr should return False if no submission"

    def test_should_open_mr_wrong_exit_status(self, open_mr_hook: OpenMRHook, agent_run_result: AgentRunResult):
        """Test should_open_mr when exit_status is not 'submitted'."""
        agent_run_result.info["exit_status"] = "failed"
        result = open_mr_hook.should_open_mr(agent_run_result)
        assert not result, "should_open_mr should return False if exit_status is not 'submitted'"

    def test_should_open_mr_no_gitlab_url_in_problem_statement(
        self, open_mr_hook: OpenMRHook, agent_run_result: AgentRunResult
    ):
        """Test should_open_mr when problem_statement has no gitlab_url."""
        delattr(open_mr_hook._problem_statement, "gitlab_url")  # type: ignore[misc]
        result = open_mr_hook.should_open_mr(agent_run_result)
        assert not result, "should_open_mr should return False if no gitlab_url"

    @mock.patch("sweagent.run.hooks.open_pr_gitlab._is_gitlab_issue_url", return_value=False)
    def test_should_open_mr_invalid_gitlab_issue_url(
        self, mock_is_gitlab_issue_url: Mock, open_mr_hook: OpenMRHook, agent_run_result: AgentRunResult
    ):
        """Test should_open_mr when gitlab_url is not a valid issue URL."""
        result = open_mr_hook.should_open_mr(agent_run_result)
        assert not result, "should_open_mr should return False for invalid gitlab_url"

    @mock.patch("sweagent.utils.gitlab._get_project_id", return_value="123")
    @mock.patch("sweagent.utils.gitlab._get_gitlab_api_client")
    @mock.patch(
        "sweagent.utils.gitlab._parse_gitlab_issue_url",
        return_value=("https://gitlab.com", "jpaodev", "test-repo", "1"),
    )
    @mock.patch("sweagent.utils.gitlab._is_gitlab_issue_url", return_value=True)
    def test_should_open_mr_gitlab_issue_assigned(
        self,
        mock_is_issue: Mock,
        mock_parse_url: Mock,
        mock_api_client: Mock,
        mock_project_id: Mock,
        agent_run_result: AgentRunResult,
        open_mr_hook: OpenMRHook,
    ):
        """Test should_open_mr with assigned GitLab issue"""
        mock_client = {"get": mock.Mock()}

        def get_side_effect(*args: str, **kwargs: dict[str, Any]) -> dict[str, Any] | list[Any]:
            if args[0].endswith("/issues/1"):
                return {
                    "iid": 1,
                    "title": "Test Issue",
                    "state": "opened",
                    "assignee": {"id": 123},  # Issue is assigned
                    "discussion_locked": False,
                }
            return []

        mock_client["get"].side_effect = get_side_effect
        mock_api_client.return_value = mock_client
        result = open_mr_hook.should_open_mr(agent_run_result)
        assert not result, "should_open_mr should return False for assigned issue"

    @mock.patch("sweagent.utils.gitlab._get_project_id", return_value="123")
    @mock.patch("sweagent.utils.gitlab._get_gitlab_api_client")
    @mock.patch(
        "sweagent.utils.gitlab._parse_gitlab_issue_url",
        return_value=("https://gitlab.com", "jpaodev", "test-repo", "1"),
    )
    @mock.patch("sweagent.utils.gitlab._is_gitlab_issue_url", return_value=True)
    def test_should_open_mr_gitlab_issue_locked(
        self,
        mock_is_issue: Mock,
        mock_parse_url: Mock,
        mock_api_client: Mock,
        mock_project_id: Mock,
        agent_run_result: AgentRunResult,
        open_mr_hook: OpenMRHook,
    ):
        """Test should_open_mr with locked GitLab issue"""
        mock_client = {"get": mock.Mock()}

        def get_side_effect(*args: str, **kwargs: dict[str, Any]) -> dict[str, Any] | list[Any]:
            if args[0].endswith("/issues/1"):
                return {
                    "iid": 1,
                    "title": "Test Issue",
                    "state": "opened",
                    "assignee": None,
                    "discussion_locked": True,  # Issue is locked
                }
            return []

        mock_client["get"].side_effect = get_side_effect
        mock_api_client.return_value = mock_client
        result = open_mr_hook.should_open_mr(agent_run_result)
        assert not result, "should_open_mr should return False for locked issue"

    @mock.patch("sweagent.run.hooks.open_pr_gitlab._get_gitlab_issue_data", side_effect=InvalidGitlabURL)
    @mock.patch("sweagent.utils.gitlab._is_gitlab_issue_url", return_value=True)  # Ensure this mock is active
    def test_should_open_mr_gitlab_invalid_url_exception(
        self, mock_is_url: Mock, mock_get_issue_data: Mock, open_mr_hook: OpenMRHook, agent_run_result: AgentRunResult
    ):
        """Test should_open_mr when _get_gitlab_issue_data raises InvalidGitlabURL."""
        # Ensure problem_statement.gitlab_url is set, which is a prerequisite for calling _get_gitlab_issue_data
        open_mr_hook._problem_statement.gitlab_url = "https://gitlab.com/jpaodev/test-repo/-/issues/1"  # type: ignore[misc]
        result = open_mr_hook.should_open_mr(agent_run_result)
        assert not result, "should_open_mr should return False if InvalidGitlabURL is raised"


@pytest.fixture
def open_mr_hook_ready_for_mr_check(open_mr_hook: OpenMRHook) -> Generator[OpenMRHook, None, None]:
    """Fixture to set up OpenMRHook with mocks for successful GitLab issue data retrieval."""
    # Ensure problem_statement.gitlab_url is set (already done in open_mr_hook fixture, but good to be explicit)
    # open_mr_hook._problem_statement.gitlab_url = "https://gitlab.com/jpaodev/test-repo/-/issues/1" # type: ignore[misc]

    patcher_is_issue_url = mock.patch("sweagent.run.hooks.open_pr_gitlab._is_gitlab_issue_url", return_value=True)
    mock_issue_data = {
        "iid": "1",
        "title": "Test Issue",
        "description": "Test Description",
        "state": "opened",
        "assignee": None,
        "discussion_locked": False,
        "web_url": "https://gitlab.com/jpaodev/test-repo/-/issues/1",
    }
    patcher_get_issue_data = mock.patch(
        "sweagent.run.hooks.open_pr_gitlab._get_gitlab_issue_data", return_value=mock_issue_data
    )

    _ = patcher_is_issue_url.start()
    _ = patcher_get_issue_data.start()

    yield open_mr_hook

    patcher_is_issue_url.stop()
    patcher_get_issue_data.stop()


class TestOpenMRHookOnInstanceCompleted:
    """Tests for the on_instance_completed method of OpenMRHook."""

    @pytest.fixture
    def agent_run_result_for_mr(self) -> AgentRunResult:
        """Create an AgentRunResult that should trigger MR creation."""
        return AgentRunResult(
            info={"submission": "Test Submission", "exit_status": "submitted"},
            trajectory=[
                {
                    "action": "test_action",
                    "observation": "test_observation",
                    "response": "test_response",
                    "state": {"key": "value"},
                    "thought": "test_thought",
                    "execution_time": 0.1,
                    "messages": [],
                    "extra_info": {},
                },
            ],
        )

    @mock.patch("sweagent.run.hooks.open_pr_gitlab.open_mr")
    def test_on_instance_completed_no_mr_when_should_not(self, mock_open_mr: Mock, open_mr_hook: OpenMRHook):
        """Test that on_instance_completed doesn't call open_mr when should_open_mr returns False."""
        # Mock should_open_mr to return False
        with mock.patch.object(open_mr_hook, "should_open_mr", return_value=False):
            # Call on_instance_completed
            result = AgentRunResult(info={}, trajectory=[])  # Initialize AgentRunResult with info and trajectory
            open_mr_hook.on_instance_completed(result)

            # Verify open_mr was not called
            assert mock_open_mr.call_count == 0

    @mock.patch("sweagent.run.hooks.open_pr_gitlab.open_mr")
    def test_on_instance_completed_no_gitlab_url(self, mock_open_mr: Mock, open_mr_hook: OpenMRHook):
        """Test that on_instance_completed logs warning when no gitlab_url is present."""
        # Mock should_open_mr to return True but remove gitlab_url
        with mock.patch.object(open_mr_hook, "should_open_mr", return_value=True):
            # Remove gitlab_url from problem_statement
            delattr(open_mr_hook._problem_statement, "gitlab_url")  # type: ignore[misc]

            # Mock logger to check warning
            mock_logger = Mock()
            open_mr_hook.logger = mock_logger

            # Call on_instance_completed
            result = AgentRunResult(info={}, trajectory=[])
            open_mr_hook.on_instance_completed(result)

            # Verify open_mr was not called and warning was logged
            assert mock_open_mr.call_count == 0
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "No GitLab issue URL found" in warning_msg


class TestOpenMRHookShouldOpenMRFinalChecks:
    @pytest.fixture
    def prepared_agent_run_result(self, agent_run_result: AgentRunResult) -> AgentRunResult:
        """Prepare agent_run_result with required submission data."""
        agent_run_result.info["submission"] = "Test Submission"
        agent_run_result.info["exit_status"] = "submitted"
        return agent_run_result


class TestOpenMR:
    """Tests for the open_mr function."""

    @pytest.fixture
    def mock_env(self) -> Mock:
        """Mock SWE environment."""
        mock_env = Mock(spec=SWEEnv)
        mock_env.communicate.return_value = "mocked output"
        return mock_env

    @pytest.fixture
    def mock_trajectory(self) -> list[dict[str, Any]]:
        """Mock trajectory data."""
        return [
            {"action": "test_action", "observation": "test_observation"},
            {"action": "another_action", "observation": "another_observation"},
        ]

    @pytest.fixture
    def gitlab_issue_url(self) -> str:
        """GitLab issue URL for testing."""
        return "https://gitlab.com/jpaodev/test-repo/-/issues/1"

    @patch("sweagent.run.hooks.open_pr_gitlab._get_gitlab_issue_data")
    @patch("sweagent.run.hooks.open_pr_gitlab._parse_gitlab_issue_url")
    @patch("sweagent.run.hooks.open_pr_gitlab.create_merge_request")
    @patch("sweagent.run.hooks.open_pr_gitlab.format_trajectory_markdown")
    @patch("sweagent.run.hooks.open_pr_gitlab.random.random")
    def test_open_mr_success(
        self,
        mock_random: Mock,
        mock_format_trajectory: Mock,
        mock_create_mr: Mock,
        mock_parse_url: Mock,
        mock_get_issue_data: Mock,
        mock_env: Mock,
        mock_trajectory: list[dict[str, Any]],
        gitlab_issue_url: str,
    ):
        """Test successful MR creation."""
        # Setup mocks
        mock_random.return_value = 0.12345678
        mock_format_trajectory.return_value = "# Formatted Trajectory\n\nSome actions"
        mock_create_mr.return_value = {"web_url": "https://gitlab.com/jpaodev/test-repo/-/merge_requests/1"}
        mock_parse_url.return_value = ("https://gitlab.com", "jpaodev", "test-repo", "1")
        mock_get_issue_data.return_value = {
            "iid": "1",
            "title": "Test Issue",
            "description": "Test Description",
            "state": "opened",
            "web_url": gitlab_issue_url,
        }

        # Mock logger
        mock_logger = Mock()

        # Call the function
        open_mr(
            logger=mock_logger,
            token="test_token",
            token_type="oauth2",
            env=mock_env,
            gitlab_url=gitlab_issue_url,
            trajectory=mock_trajectory,
        )

        # Verify the expected calls were made
        assert mock_env.communicate.call_count >= 4, "Should make multiple git commands"
        assert mock_create_mr.call_count == 1, "Should create one merge request"

        # Verify merge request creation parameters
        mr_call_kwargs = mock_create_mr.call_args[1]
        assert mr_call_kwargs["gitlab_instance"] == "https://gitlab.com"
        assert mr_call_kwargs["owner"] == "jpaodev"
        assert mr_call_kwargs["repo"] == "test-repo"
        assert "swe-agent-fix-#1-12345678" in mr_call_kwargs["source_branch"]
        assert mr_call_kwargs["target_branch"] == "main"
        assert "Test Issue" in mr_call_kwargs["title"]
        assert "Closes #1" in mr_call_kwargs["description"]
        assert mr_call_kwargs["token"] == "test_token"
        assert mr_call_kwargs["token_type"] == "oauth2"
        assert mr_call_kwargs["draft"] is True

    @patch("sweagent.run.hooks.open_pr_gitlab._get_gitlab_issue_data")
    def test_open_mr_invalid_url(
        self,
        mock_get_issue_data: Mock,
        mock_env: Mock,
        mock_trajectory: list[dict[str, Any]],
        gitlab_issue_url: str,
    ):
        """Test MR creation with invalid GitLab URL."""
        # Setup mock to raise exception
        mock_get_issue_data.side_effect = InvalidGitlabURL("Invalid URL")

        # Mock logger
        mock_logger = Mock()

        # Call the function and expect exception
        with pytest.raises(ValueError, match="Data path must be a GitLab issue URL"):
            open_mr(
                logger=mock_logger,
                token="test_token",
                token_type="oauth2",
                env=mock_env,
                gitlab_url=gitlab_issue_url,
                trajectory=mock_trajectory,
            )

    @patch("sweagent.run.hooks.open_pr_gitlab._get_gitlab_issue_data")
    @patch("sweagent.run.hooks.open_pr_gitlab._parse_gitlab_issue_url")
    @patch("sweagent.run.hooks.open_pr_gitlab.create_merge_request")
    @patch("sweagent.run.hooks.open_pr_gitlab.format_trajectory_markdown")
    @patch("sweagent.run.hooks.open_pr_gitlab.random.random")
    def test_open_mr_dry_run(
        self,
        mock_random: Mock,
        mock_format_trajectory: Mock,
        mock_create_mr: Mock,
        mock_parse_url: Mock,
        mock_get_issue_data: Mock,
        mock_env: Mock,
        mock_trajectory: list[dict[str, Any]],
        gitlab_issue_url: str,
    ):
        """Test MR creation in dry run mode."""
        # Setup mocks
        mock_random.return_value = 0.12345678
        mock_format_trajectory.return_value = "# Formatted Trajectory\n\nSome actions"
        mock_parse_url.return_value = ("https://gitlab.com", "jpaodev", "test-repo", "1")
        mock_get_issue_data.return_value = {
            "iid": "1",
            "title": "Test Issue",
            "description": "Test Description",
            "state": "opened",
            "web_url": gitlab_issue_url,
        }

        # Mock logger
        mock_logger = Mock()

        # Call the function with dry run
        open_mr(
            logger=mock_logger,
            token="test_token",
            token_type="oauth2",
            env=mock_env,
            gitlab_url=gitlab_issue_url,
            trajectory=mock_trajectory,
            _dry_run=True,
        )

        # Verify create_merge_request was not called
        assert mock_create_mr.call_count == 0, "Should not create merge request in dry run mode"

        # Verify git commands were still called
        assert mock_env.communicate.call_count >= 4, "Should make git commands even in dry run mode"

    @patch("sweagent.run.hooks.open_pr_gitlab._get_gitlab_issue_data")
    @patch("sweagent.run.hooks.open_pr_gitlab._parse_gitlab_issue_url")
    @patch("sweagent.run.hooks.open_pr_gitlab.create_merge_request")
    @patch("sweagent.run.hooks.open_pr_gitlab.format_trajectory_markdown")
    @patch("sweagent.run.hooks.open_pr_gitlab.random.random")
    def test_open_mr_error_handling(
        self,
        mock_random: Mock,
        mock_format_trajectory: Mock,
        mock_create_mr: Mock,
        mock_parse_url: Mock,
        mock_get_issue_data: Mock,
        mock_env: Mock,
        mock_trajectory: list[dict[str, Any]],
        gitlab_issue_url: str,
    ):
        """Test error handling during MR creation."""
        # Setup mocks
        mock_random.return_value = 0.12345678
        mock_format_trajectory.return_value = "# Formatted Trajectory\n\nSome actions"
        mock_parse_url.return_value = ("https://gitlab.com", "jpaodev", "test-repo", "1")
        mock_get_issue_data.return_value = {
            "iid": "1",
            "title": "Test Issue",
            "description": "Test Description",
            "state": "opened",
            "web_url": gitlab_issue_url,
        }
        # Make create_merge_request raise an exception
        mock_create_mr.side_effect = Exception("API error")

        # Mock logger
        mock_logger = Mock()

        # Call the function - should not raise exception
        open_mr(
            logger=mock_logger,
            token="test_token",
            token_type="oauth2",
            env=mock_env,
            gitlab_url=gitlab_issue_url,
            trajectory=mock_trajectory,
        )

        # Verify error was logged
        mock_logger.error.assert_called_once()
        error_msg = mock_logger.error.call_args[0][0]
        assert "Failed to create GitLab merge request" in error_msg
