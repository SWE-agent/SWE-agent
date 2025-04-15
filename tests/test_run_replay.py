from __future__ import annotations

import subprocess

import pytest
from swerex.deployment.config import DockerDeploymentConfig

from sweagent.run.run_replay import RunReplay, RunReplayConfig


@pytest.fixture
def rr_config(swe_agent_test_repo_traj, tmp_path, swe_agent_test_repo_clone):
    return RunReplayConfig(
        traj_path=swe_agent_test_repo_traj,
        deployment=DockerDeploymentConfig(image="python:3.13-slim"),
        output_dir=tmp_path,
    )


def test_replay(rr_config):
    rr = RunReplay.from_config(rr_config, _catch_errors=False, _require_zero_exit_code=True)
    rr.main()


def test_run_cli_help():
    args = [
        "sweagent",
        "run-replay",
        "--help",
    ]
    output = subprocess.run(args, capture_output=True)
    assert output.returncode == 0
    assert "Replay a trajectory file" in output.stdout.decode()
