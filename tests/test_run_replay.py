from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from swerex.deployment.config import DockerDeploymentConfig, DummyDeploymentConfig

from sweagent.run.run_replay import RunReplay, RunReplayConfig, run_from_config


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


def test_run_cli_help():
    args = [
        "sweagent",
        "run-replay",
        "--help",
    ]
    output = subprocess.run(args, capture_output=True)
    assert output.returncode == 0
    assert "Replay a trajectory file" in output.stdout.decode()


def test_validate_only_does_not_create_deployment_or_output(
    swe_agent_test_repo_traj: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    output_dir = tmp_path / "replay-output"

    def fail_get_deployment(*args, **kwargs):
        pytest.fail("validate-only must not create a deployment")

    monkeypatch.setattr("sweagent.run.run_replay.get_deployment", fail_get_deployment)
    config = RunReplayConfig(
        traj_path=swe_agent_test_repo_traj,
        deployment=DummyDeploymentConfig(),
        output_dir=output_dir,
        validate_only=True,
    )

    run_from_config(config)

    assert not output_dir.exists()


def test_validate_only_rejects_trajectory_without_actions(swe_agent_test_repo_traj: Path, tmp_path: Path):
    traj_path = tmp_path / "invalid.traj"
    traj_data = json.loads(swe_agent_test_repo_traj.read_text())
    traj_data["history"] = []
    traj_path.write_text(json.dumps(traj_data))
    config = RunReplayConfig(traj_path=traj_path, output_dir=tmp_path / "output", validate_only=True)

    with pytest.raises(ValueError, match="No actions found in trajectory"):
        run_from_config(config)
