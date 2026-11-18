from __future__ import annotations

import json

import pytest

from sweagent.run import inspector_cli


@pytest.fixture
def trajectory_dir(tmp_path):
    traj_dir = tmp_path / "trajectories"
    traj_dir.mkdir()
    (traj_dir / "instance-1.traj").write_text(json.dumps({"trajectory": [], "history": [], "info": {}}))
    return traj_dir


@pytest.fixture
def swebench_dataset(tmp_path):
    """A SWE-bench style dataset, i.e. a list of instance records (``load_file`` keeps the list)."""
    data_path = tmp_path / "swe-bench-lite-test.json"
    data_path.write_text(json.dumps([{"instance_id": "instance-1", "patch": "gold patch"}]))
    return data_path


def test_main_forwards_data_path(trajectory_dir, swebench_dataset, monkeypatch):
    captured = {}

    class _RecordingApp:
        def __init__(self, input_path, data_path=None):
            captured["input_path"] = input_path
            captured["data_path"] = data_path

        def run(self):
            captured["ran"] = True

    monkeypatch.setattr(inspector_cli, "TrajectoryInspectorApp", _RecordingApp)
    inspector_cli.main([str(trajectory_dir), "--data_path", str(swebench_dataset)])
    assert captured["data_path"] == swebench_dataset
    assert captured["ran"] is True


def test_dataset_records_are_used_for_gold_patches(trajectory_dir, swebench_dataset):
    app = inspector_cli.TrajectoryInspectorApp(trajectory_dir, data_path=swebench_dataset)
    assert app.get_gold_patch("instance-1") == "gold patch"
    assert app.get_gold_patch("instance-2") is None
