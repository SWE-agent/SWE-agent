from __future__ import annotations

from pathlib import Path

import pytest

from sweagent import CONFIG_DIR, TOOLS_DIR
from sweagent.agent.agents import DefaultAgentConfig
from sweagent.agent.models import InstantEmptySubmitModelConfig
from sweagent.environment.swe_env import EnvironmentConfig
from sweagent.run.common import BasicCLI
from sweagent.run.hooks.abstract import RunHook
from sweagent.run.run_single import RunSingle, RunSingleConfig
from sweagent.tools.bundle import Bundle


class RaisesExceptionHook(RunHook):
    def on_instance_start(self, *args, **kwargs):
        msg = "test exception"
        raise ValueError(msg)


@pytest.mark.slow
def test_run_single_raises_exception():
    rsc = RunSingleConfig(agent=DefaultAgentConfig(model=InstantEmptySubmitModelConfig()))
    rs = RunSingle.from_config(rsc)
    rs.add_hook(RaisesExceptionHook())
    with pytest.raises(ValueError, match="test exception"):
        rs.run()


@pytest.fixture
def agent_config_with_commands():
    ac = DefaultAgentConfig(model=InstantEmptySubmitModelConfig())
    ac.tools.bundles = [
        Bundle(path=TOOLS_DIR / "registry"),
        Bundle(path=TOOLS_DIR / "windowed"),
        Bundle(path=TOOLS_DIR / "submit"),
    ]
    ac.tools.env_variables = {"WINDOW": 100}
    assert (TOOLS_DIR / "submit").exists()
    # Make sure dependent properties are set
    ac.tools.model_post_init(None)
    return ac


@pytest.mark.slow
def test_hidden_tools(tmpdir):
    ac = DefaultAgentConfig(model=InstantEmptySubmitModelConfig())
    ac.tools.env_variables = {"WINDOW": 100}
    ac.tools.bundles = [
        Bundle(path=TOOLS_DIR / "registry"),
        Bundle(path=TOOLS_DIR / "windowed", hidden_tools=["scroll_up"]),
        Bundle(path=TOOLS_DIR / "submit"),
    ]
    ac.model.name = "instant_empty_submit"
    rsc = RunSingleConfig(
        env=EnvironmentConfig(),
        agent=ac,
        output_dir=Path(tmpdir),
    )
    rs = RunSingle.from_config(rsc)
    rs.run()


@pytest.mark.slow
def test_run_ies(tmpdir, agent_config_with_commands):
    # ies = instant empty submit
    ac = agent_config_with_commands
    ac.model.name = "instant_empty_submit"
    rsc = RunSingleConfig(
        env=EnvironmentConfig(),
        agent=ac,
        output_dir=Path(tmpdir),
    )
    rs = RunSingle.from_config(rsc)
    rs.agent.tools.mock_state = {"open_file": "asdf123", "working_dir": "/root"}
    rs.run()


@pytest.mark.slow
@pytest.mark.parametrize("repo", ["local", "github"])
@pytest.mark.parametrize("problem_statement_source", ["github", "local", "text"])
def test_run_ies_repo_ps_matrix(
    tmpdir,
    swe_agent_test_repo_clone,
    repo,
    problem_statement_source,
):
    output_formats = ["traj", "pred", "patch"]
    for fmt in output_formats:
        assert not list(Path(tmpdir).glob(f"*.{fmt}"))
    if problem_statement_source == "github":
        ps_args = ["--problem_statement.github_url", "https://github.com/swe-agent/test-repo/issues/1"]
    elif problem_statement_source == "local":
        ps_args = ["--problem_statement.path", str(swe_agent_test_repo_clone / "problem_statements" / "1.md")]
    elif problem_statement_source == "text":
        ps_args = ["--problem_statement.text='this is a test'"]
    else:
        raise ValueError(problem_statement_source)
    if repo == "local":
        repo_args = ["--env.repo.path", str(swe_agent_test_repo_clone)]
    elif repo == "github":
        repo_args = ["--env.repo.github_url", "https://github.com/swe-agent/test-repo"]
    else:
        raise ValueError(repo)
    args = [
        "--agent.model.name=instant_empty_submit",
        "--output_dir",
        str(tmpdir),
        *ps_args,
        *repo_args,
        "--config",
        str(CONFIG_DIR / "default_backticks.yaml"),
    ]
    print(args)
    rs_config = BasicCLI(RunSingleConfig).get_config(args)
    print(rs_config)
    rs = RunSingle.from_config(rs_config)  # type: ignore
    with tmpdir.as_cwd():
        # Test that we can run run.py also independently from repo dir
        rs.run()
    for fmt in output_formats:
        print(fmt, list(Path(tmpdir).iterdir()))
        assert len(list(Path(tmpdir).rglob(f"*.{fmt}"))) == 1


@pytest.mark.slow
@pytest.mark.parametrize("submit_method", ["normal_submission", "file_submission"])
def test_run_submit_matrix(
    tmpdir,
    submit_method,
):
    # Define expected output files based on submit method
    if submit_method == "file_submission":
        output_formats = ["traj", "pred"]
        expected_files = ["README.md"]
    else:  # normal_submission
        output_formats = ["traj", "pred", "patch"]
        expected_files = []

    # Check that output files don't exist initially
    for fmt in output_formats:
        assert not list(Path(tmpdir).glob(f"*.{fmt}"))
    for file in expected_files:
        assert not list(Path(tmpdir).glob(file))

    if submit_method == "file_submission":
        ps_args = ["--problem_statement.text='file_submission test'"]
    elif submit_method == "normal_submission":
        ps_args = ["--problem_statement.text='this is a test'"]
    else:
        raise ValueError(submit_method)
    repo_args = ["--env.repo.github_url", "https://github.com/swe-agent/test-repo"]

    # NOTE: config/bash_only.yaml is used here to verify the submit command
    # If you find this test case failing, it may be related to the changes in bash_only.yaml

    args = [
        "--agent.model.name=instant_empty_submit",
        "--output_dir",
        str(tmpdir),
        *ps_args,
        *repo_args,
        "--config",
        str(CONFIG_DIR / "bash_only.yaml"),
        "--agent.tools.parse_function.type=thought_action"
    ]
    print(args)
    rs_config = BasicCLI(RunSingleConfig).get_config(args)
    print(rs_config)
    rs = RunSingle.from_config(rs_config)  # type: ignore
    with tmpdir.as_cwd():
        # Test that we can run run.py also independently from repo dir
        rs.run()

    # Check that expected output files were created
    for fmt in output_formats:
        print(fmt, list(Path(tmpdir).iterdir()))
        assert len(list(Path(tmpdir).rglob(f"*.{fmt}"))) == 1

    # Check for additional expected files (like reproduce.py for file_submission)
    for file in expected_files:
        print(file, list(Path(tmpdir).iterdir()))
        assert len(list(Path(tmpdir).rglob(file))) == 1
