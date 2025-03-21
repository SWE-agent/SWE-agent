from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

from sweagent import CONFIG_DIR, TOOLS_DIR
from sweagent.agent.agents import DefaultAgentConfig
from sweagent.agent.models import InstantEmptySubmitModelConfig
from sweagent.agent.problem_statement import GitlabIssue, problem_statement_from_simplified_input
from sweagent.environment.repo import GitlabRepoConfig, repo_from_simplified_input
from sweagent.run.common import BasicCLI
from sweagent.run.run_single import RunSingle, RunSingleConfig
from sweagent.tools.bundle import Bundle
from sweagent.utils.gitlab import (
    _is_gitlab_issue_url,
    _is_gitlab_repo_url,
    _is_gitlab_url,
    _parse_gitlab_issue_url,
    _parse_gitlab_repo_url,
)


@pytest.mark.slow
def test_gitlab_url_detection():
    """Test that GitLab URLs are correctly detected"""
    # Standard GitLab URLs
    assert _is_gitlab_url("https://gitlab.com/jpaodev/test-repo")
    assert _is_gitlab_url("https://gitlab.com/jpaodev/test-repo/-/issues/1")

    # Custom GitLab instance URLs
    assert _is_gitlab_url("https://gitlab.example.com/user/repo")

    # Non-URL should return False
    assert not _is_gitlab_url("not a url")


@pytest.mark.slow
def test_gitlab_repo_url_detection():
    """Test that GitLab repository URLs are correctly detected"""
    # Standard GitLab repo URLs
    assert _is_gitlab_repo_url("https://gitlab.com/jpaodev/test-repo")
    assert _is_gitlab_repo_url("https://gitlab.com/jpaodev/test-repo.git")
    assert _is_gitlab_repo_url("git@gitlab.com:jpaodev/test-repo.git")

    # Non-repo URLs should return False
    assert not _is_gitlab_repo_url("https://gitlab.com")
    assert not _is_gitlab_repo_url("not a url")


@pytest.mark.slow
def test_gitlab_issue_url_detection():
    """Test that GitLab issue URLs are correctly detected"""
    # Standard GitLab issue URLs
    assert _is_gitlab_issue_url("https://gitlab.com/jpaodev/test-repo/-/issues/1")

    # Non-issue URLs should return False
    assert not _is_gitlab_issue_url("https://gitlab.com/jpaodev/test-repo")
    assert not _is_gitlab_issue_url("not a url")


@pytest.mark.slow
def test_gitlab_url_parsing():
    """Test that GitLab URLs are correctly parsed"""
    # Test repository URL parsing
    gitlab_instance, owner, repo = _parse_gitlab_repo_url("https://gitlab.com/jpaodev/test-repo")
    assert gitlab_instance == "gitlab.com"
    assert owner == "jpaodev"
    assert repo == "test-repo"

    # Test issue URL parsing
    gitlab_instance, owner, repo, issue_number = _parse_gitlab_issue_url(
        "https://gitlab.com/jpaodev/test-repo/-/issues/1"
    )
    assert gitlab_instance == "https://gitlab.com"
    assert owner == "jpaodev"
    assert repo == "test-repo"
    assert issue_number == "1"


@pytest.mark.slow
def test_gitlab_problem_statement():
    """Test GitlabIssue problem statement initialization"""
    # Create a GitlabIssue
    issue = GitlabIssue(gitlab_url="https://gitlab.com/jpaodev/test-repo/-/issues/1")

    # Check that the ID is correctly generated
    assert "gitlab" in issue.id
    assert "jpaodev" in issue.id
    assert "test-repo" in issue.id

    # Check the type
    assert issue.type == "gitlab"


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
@pytest.mark.parametrize("problem_statement_source", ["gitlab", "text"])
@mock.patch.dict(os.environ, {"GITLAB_TOKEN": "test_token", "GITLAB_TOKEN_TYPE": "project"})
def test_run_gitlab_matrix(tmpdir, swe_agent_test_repo_clone, problem_statement_source):
    """Test running with GitLab repository and different problem statement sources"""
    output_formats = ["traj", "pred", "patch"]
    for fmt in output_formats:
        assert not list(Path(tmpdir).glob(f"*.{fmt}"))

    # Set up problem statement arguments based on source
    if problem_statement_source == "gitlab":
        ps_args = ["--problem_statement.gitlab_url", "https://gitlab.com/jpaodev/test-repo/-/issues/1"]
    elif problem_statement_source == "text":
        ps_args = ["--problem_statement.text='This is a test for GitLab integration'"]
    else:
        msg = f"Unsupported problem statement source: {problem_statement_source}"
        raise ValueError(msg)

    # Use the local repo path from the fixture
    repo_args = ["--env.repo.path", str(swe_agent_test_repo_clone)]

    # Create arguments for RunSingleConfig
    args = [
        "--agent.model.name=instant_empty_submit",
        "--output_dir",
        str(tmpdir),
        *ps_args,
        *repo_args,
        "--config",
        str(CONFIG_DIR / "default_no_fcalls.yaml"),
    ]

    # Create RunSingleConfig
    rs_config = BasicCLI(RunSingleConfig).get_config(args)

    # Mock the problem statement to avoid API calls
    with mock.patch(
        "sweagent.agent.problem_statement.GitlabIssue.get_problem_statement",
        return_value="Test Issue\nThis is a test issue description\n",
    ):
        # Create RunSingle
        rs = RunSingle.from_config(rs_config)

        # Run the test
        with tmpdir.as_cwd():
            rs.run()

    # Check that output files were created
    for fmt in output_formats:
        assert len(list(Path(tmpdir).rglob(f"*.{fmt}"))) == 1


@pytest.mark.slow
def test_problem_statement_from_simplified_input_gitlab():
    """Test problem_statement_from_simplified_input with GitLab URLs"""
    # Test with explicit gitlab_issue type
    ps = problem_statement_from_simplified_input(
        input="https://gitlab.com/jpaodev/test-repo/-/issues/1", type="gitlab_issue"
    )
    assert isinstance(ps, GitlabIssue)
    assert ps.gitlab_url == "https://gitlab.com/jpaodev/test-repo/-/issues/1"

    # Test with auto-detection (issue type)
    ps = problem_statement_from_simplified_input(input="https://gitlab.com/jpaodev/test-repo/-/issues/1", type="issue")
    assert isinstance(ps, GitlabIssue)
    assert ps.gitlab_url == "https://gitlab.com/jpaodev/test-repo/-/issues/1"
