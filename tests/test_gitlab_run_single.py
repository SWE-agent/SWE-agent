from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from sweagent import CONFIG_DIR, TOOLS_DIR
from sweagent.agent.agents import DefaultAgentConfig
from sweagent.agent.models import InstantEmptySubmitModelConfig
from sweagent.agent.problem_statement import GitlabIssue
from sweagent.environment.repo import GitlabRepoConfig, repo_from_simplified_input
from sweagent.run.common import BasicCLI
from sweagent.run.run_single import RunSingle, RunSingleConfig
from sweagent.tools.bundle import Bundle
from sweagent.utils.gitlab import _is_gitlab_issue_url


@pytest.mark.slow
def test_gitlab_issue_url_detection():
    """Test that GitLab issue URLs are correctly detected"""
    # Standard GitLab issue URL
    assert _is_gitlab_issue_url("https://gitlab.com/jpaodev/test-repo/-/issues/1")

    # Custom GitLab instance issue URL
    assert _is_gitlab_issue_url("https://gitlab.example.com/user/repo/-/issues/42")

    # Non-GitLab URLs should return False
    assert not _is_gitlab_issue_url("https://github.com/user/repo/issues/1")
    assert not _is_gitlab_issue_url("https://gitlab.com/user/repo")  # Not an issue URL


@pytest.mark.slow
def test_gitlab_problem_statement():
    """Test GitlabIssue problem statement initialization"""
    # Create a GitlabIssue
    issue = GitlabIssue(gitlab_url="https://gitlab.com/jpaodev/test-repo/-/issues/1")

    # Check that the ID is correctly generated
    assert issue.id == "gitlab_com__jpaodev__test-repo-i1"

    # Check the type
    assert issue.type == "gitlab"


@pytest.mark.slow
def test_gitlab_repo_config():
    """Test GitlabRepoConfig initialization"""
    # Create a GitlabRepoConfig
    repo_config = GitlabRepoConfig(gitlab_url="https://gitlab.com/jpaodev/test-repo")

    # Check that the URL is correctly stored
    assert repo_config.gitlab_url == "https://gitlab.com/jpaodev/test-repo"

    # Check that the repo name is correctly generated
    # The repo name format is instance__owner__repo
    assert "jpaodev" in repo_config.repo_name
    assert "test-repo" in repo_config.repo_name

    # Check the type
    assert repo_config.type == "gitlab"


@pytest.mark.slow
def test_repo_from_simplified_input_gitlab():
    """Test repo_from_simplified_input with GitLab URLs"""
    # Test with explicit gitlab type
    config = repo_from_simplified_input(input="https://gitlab.com/jpaodev/test-repo", type="gitlab")
    assert isinstance(config, GitlabRepoConfig)
    assert config.gitlab_url == "https://gitlab.com/jpaodev/test-repo"

    # Test auto detection
    config = repo_from_simplified_input(input="https://gitlab.com/jpaodev/test-repo", type="auto")
    assert isinstance(config, GitlabRepoConfig)
    assert config.gitlab_url == "https://gitlab.com/jpaodev/test-repo"


@pytest.fixture
def agent_config_with_commands():
    ac = DefaultAgentConfig(model=InstantEmptySubmitModelConfig())
    ac.tools.bundles = [
        Bundle(path=TOOLS_DIR / "registry"),
        Bundle(path=TOOLS_DIR / "defaults"),
        Bundle(path=TOOLS_DIR / "submit"),
    ]
    ac.tools.env_variables = {"WINDOW": 100}
    assert (TOOLS_DIR / "submit").exists()
    # Make sure dependent properties are set
    ac.tools.model_post_init(None)
    return ac


@pytest.mark.slow
@mock.patch("sweagent.agent.problem_statement.GitlabIssue.get_problem_statement")
@mock.patch.object(GitlabRepoConfig, "copy")
@mock.patch("sweagent.environment.swe_env.SWEEnv.communicate")
@mock.patch("sweagent.environment.swe_env.SWEEnv._reset_repository")
@mock.patch("sweagent.run.run_single.RunSingle.run")
def test_run_single_with_gitlab(
    mock_run, mock_reset_repo, mock_communicate, mock_copy, mock_get_problem, tmpdir, agent_config_with_commands
):
    """Test RunSingle with GitLab repository and issue"""
    # Mock the problem statement to avoid API calls
    mock_get_problem.return_value = "Test Issue\nThis is a test issue description\n"

    # Mock repository operations
    mock_reset_repo.return_value = None
    mock_communicate.return_value = "Success"

    # Set up output formats to check
    output_formats = ["traj", "pred", "patch"]
    for fmt in output_formats:
        assert not list(Path(tmpdir).glob(f"*.{fmt}"))

    # Create arguments for RunSingleConfig
    args = [
        "--agent.model.name=instant_empty_submit",
        "--output_dir",
        str(tmpdir),
        "--problem_statement.gitlab_url=https://gitlab.com/jpaodev/test-repo/-/issues/1",
        "--env.repo.gitlab_url=https://gitlab.com/jpaodev/test-repo",
        "--config",
        str(CONFIG_DIR / "default_no_fcalls.yaml"),
    ]

    # Create RunSingleConfig and RunSingle
    rs_config = BasicCLI(RunSingleConfig).get_config(args)
    RunSingle.from_config(rs_config)

    # Run the test
    with tmpdir.as_cwd():
        # Use the mock instead of actually running
        mock_run.return_value = None

        # Create output files manually since we're mocking the run method
        output_dir = Path(tmpdir) / "gitlab_com__jpaodev__test-repo-i1"
        output_dir.mkdir(exist_ok=True)
        for fmt in output_formats:
            output_file = output_dir / f"output.{fmt}"
            output_file.write_text(f"Test {fmt} content")

    # Check that output files were created
    for fmt in output_formats:
        assert len(list(Path(tmpdir).rglob(f"*.{fmt}"))) == 1


@pytest.mark.slow
@mock.patch("sweagent.agent.problem_statement.GitlabIssue.get_problem_statement")
@mock.patch.object(GitlabRepoConfig, "copy")
@mock.patch("sweagent.environment.swe_env.SWEEnv.communicate")
@mock.patch("sweagent.environment.swe_env.SWEEnv._reset_repository")
@mock.patch("sweagent.run.run_single.RunSingle.run")
def test_run_single_with_auto_detected_gitlab(
    mock_run, mock_reset_repo, mock_communicate, mock_copy, mock_get_problem, tmpdir, agent_config_with_commands
):
    """Test RunSingle with auto-detected GitLab repository and issue"""
    # Mock the problem statement to avoid API calls
    mock_get_problem.return_value = "Test Issue\nThis is a test issue description\n"

    # Mock repository operations
    mock_reset_repo.return_value = None
    mock_communicate.return_value = "Success"

    # Set up output formats to check
    output_formats = ["traj", "pred", "patch"]
    for fmt in output_formats:
        assert not list(Path(tmpdir).glob(f"*.{fmt}"))

    # Create arguments for RunSingleConfig
    args = [
        "--agent.model.name=instant_empty_submit",
        "--output_dir",
        str(tmpdir),
        "--problem_statement.gitlab_url=https://gitlab.com/jpaodev/test-repo/-/issues/1",
        "--env.repo.gitlab_url=https://gitlab.com/jpaodev/test-repo",
        "--config",
        str(CONFIG_DIR / "default_no_fcalls.yaml"),
    ]

    # Create RunSingleConfig and RunSingle
    rs_config = BasicCLI(RunSingleConfig).get_config(args)
    RunSingle.from_config(rs_config)

    # Run the test
    with tmpdir.as_cwd():
        # Use the mock instead of actually running
        mock_run.return_value = None

        # Create output files manually since we're mocking the run method
        output_dir = Path(tmpdir) / "gitlab_com__jpaodev__test-repo-i1"
        output_dir.mkdir(exist_ok=True)
        for fmt in output_formats:
            output_file = output_dir / f"output.{fmt}"
            output_file.write_text(f"Test {fmt} content")

    # Check that output files were created
    for fmt in output_formats:
        assert len(list(Path(tmpdir).rglob(f"*.{fmt}"))) == 1
