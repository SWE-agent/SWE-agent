from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
from swerex.deployment.config import DockerDeploymentConfig, DummyDeploymentConfig

from sweagent.environment.repo import LocalRepoConfig
from sweagent.environment.swe_env import EnvironmentConfig, SWEEnv

# this is a hack and should be removed when we have a better solution
_this_dir = Path(__file__).resolve().parent
root_dir = _this_dir.parent
package_dir = root_dir / "sweagent"
sys.path.insert(0, str(root_dir))
sys.path.insert(1, str(package_dir))


@pytest.fixture
def test_data_path() -> Path:
    p = _this_dir / "test_data"
    assert p.is_dir()
    return p


@pytest.fixture
def test_trajectories_path(test_data_path) -> Path:
    p = test_data_path / "trajectories"
    assert p.is_dir()
    return p


@pytest.fixture
def test_ctf_trajectories_path(test_data_path) -> Path:
    p = test_data_path / "trajectories" / "ctf"
    assert p.is_dir()
    return p


@pytest.fixture
def ctf_data_path(test_data_sources_path) -> Path:
    p = test_data_sources_path / "ctf"
    assert p.is_dir()
    return p


@pytest.fixture
def swe_agent_test_ctf_repo_and_ps(ctf_data_path) -> tuple[Path, Path]:
    p = ctf_data_path / "forensics" / "flash"
    ps = p / "challenge.json"
    assert p.is_dir()
    return p, ps


@pytest.fixture
def test_data_sources_path(test_data_path) -> Path:
    p = test_data_path / "data_sources"
    assert p.is_dir()
    return p


@pytest.fixture
def test_trajectory_path(test_trajectories_path) -> Path:
    traj = (
        test_trajectories_path
        / "gpt4__swe-agent__test-repo__default_from_url__t-0.00__p-0.95__c-3.00__install-1"
        / "swe-agent__test-repo-i1.traj"
    )
    assert traj.exists()
    return traj


@pytest.fixture
def test_trajectory(test_trajectory_path):
    return json.loads(test_trajectory_path.read_text())


@pytest.fixture(scope="module")
def test_env_args(
    tmpdir_factory,
) -> Generator[EnvironmentConfig]:
    """This will use a persistent container"""
    local_repo_path = tmpdir_factory.getbasetemp() / "test-repo"
    clone_cmd = ["git", "clone", "https://github.com/swe-agent/test-repo", str(local_repo_path)]
    subprocess.run(clone_cmd, check=True)
    test_env_args = EnvironmentConfig(
        deployment=DockerDeploymentConfig(image="python:3.11"),
        repo=LocalRepoConfig(path=Path(local_repo_path)),
    )
    yield test_env_args
    shutil.rmtree(local_repo_path)


@pytest.fixture
def dummy_env_args() -> EnvironmentConfig:
    return EnvironmentConfig(
        deployment=DummyDeploymentConfig(),
        repo=None,
    )


@pytest.fixture
def dummy_env(dummy_env_args) -> Generator[SWEEnv, None, None]:
    env = SWEEnv.from_config(dummy_env_args)
    env.start()
    yield env
    env.close()


@contextmanager
def swe_env_context(env_args):
    """Context manager to make sure we close the shell on the container
    so that we can reuse it.
    """

    env = SWEEnv.from_config(env_args)
    env.start()
    try:
        yield env
    finally:
        env.close()


@pytest.fixture
def swe_agent_test_repo_clone(tmp_path):
    local_repo_path = tmp_path / "test-repo"
    clone_cmd = ["git", "clone", "https://github.com/swe-agent/test-repo", local_repo_path]
    subprocess.run(clone_cmd, check=True)
    return local_repo_path


@pytest.fixture
def swe_agent_test_repo_traj(test_trajectories_path) -> Path:
    p = (
        test_trajectories_path
        / "gpt4__swe-agent-test-repo__default_from_url__t-0.00__p-0.95__c-3.00__install-1"
        / "6e44b9__sweagenttestrepo-1c2844.traj"
    )
    assert p.is_file()
    return p
