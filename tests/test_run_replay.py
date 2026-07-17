from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from swerex.deployment.abstract import AbstractDeployment
from swerex.deployment.config import DockerDeploymentConfig

from sweagent.run.run_replay import RunReplay, RunReplayConfig


@pytest.fixture
def rr_config(swe_agent_test_repo_traj, tmp_path, swe_agent_test_repo_clone):
    return RunReplayConfig(
        traj_path=swe_agent_test_repo_traj,
        deployment=DockerDeploymentConfig(image="python:3.11"),
        output_dir=tmp_path,
    )


def test_replay(rr_config):
    rr = RunReplay.from_config(rr_config, _catch_errors=False, _require_zero_exit_code=True)
    rr.main()


def test_replay_preserves_environment_config(swe_agent_test_repo_traj, tmp_path):
    traj_data = json.loads(swe_agent_test_repo_traj.read_text())
    traj_data["replay_config"]["env"].update(
        post_startup_commands=["echo setup"],
        post_startup_command_timeout=123,
        name="replay",
    )
    traj_path = tmp_path / "replay.traj"
    traj_path.write_text(json.dumps(traj_data))

    deployment = MagicMock(spec=AbstractDeployment)
    rr = RunReplay(traj_path=traj_path, deployment=deployment, output_dir=tmp_path)

    with patch("sweagent.run.run_replay.SWEEnv") as swe_env:
        rr._get_env()

    swe_env.assert_called_once_with(
        deployment=deployment,
        repo=rr.config.env.repo,
        post_startup_commands=["echo setup"],
        post_startup_command_timeout=123,
        name="replay",
    )


def test_run_cli_help():
    args = [
        "sweagent",
        "run-replay",
        "--help",
    ]
    output = subprocess.run(args, capture_output=True)
    assert output.returncode == 0
    assert "Replay a trajectory file" in output.stdout.decode()
