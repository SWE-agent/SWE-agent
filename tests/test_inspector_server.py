from __future__ import annotations

import pytest

from sweagent.inspector.server import resolve_trajectory_path


@pytest.fixture
def traj_dir(tmp_path):
    served = tmp_path / "served"
    (served / "nested").mkdir(parents=True)
    (served / "run.traj").write_text("{}")
    (served / "nested" / "run.traj").write_text("{}")
    (tmp_path / "secret.json").write_text('{"secret": "value"}')
    return served


@pytest.mark.parametrize("name", ["run.traj", "nested/run.traj", "nested%2Frun.traj"])
def test_paths_inside_the_directory_resolve(traj_dir, name):
    resolved = resolve_trajectory_path(traj_dir, name)
    assert resolved.is_file()
    assert traj_dir.resolve() in resolved.parents


@pytest.mark.parametrize(
    "name",
    [
        "../secret.json",
        "nested/../../secret.json",
        "..%2Fsecret.json",
        "../../../../../../etc/passwd",
    ],
)
def test_parent_segments_are_rejected(traj_dir, name):
    with pytest.raises(FileNotFoundError):
        resolve_trajectory_path(traj_dir, name)


def test_absolute_paths_are_rejected(traj_dir, tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_trajectory_path(traj_dir, str(tmp_path / "secret.json"))


def test_query_string_is_stripped(traj_dir):
    assert resolve_trajectory_path(traj_dir, "run.traj?cache=0").is_file()
