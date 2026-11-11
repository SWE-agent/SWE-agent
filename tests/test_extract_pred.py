import json
from pathlib import Path

import pytest

from sweagent.run.run import main


@pytest.mark.parametrize(
    ("relative_path", "run_name", "instance_id"),
    [
        ("run/instance/instance.traj", "run", "instance"),
        ("run/instance/attempt_0/instance.traj", "run", "instance"),
        ("run/instance/attempt_12/instance.traj", "run", "instance"),
        ("root/attempt_0/attempt_0/attempt_0.traj", "attempt_0", "attempt_0"),
        ("root/instance/attempt_manual/instance.traj", "instance", "attempt_manual"),
        ("root/other/attempt_0/instance.traj", "other", "attempt_0"),
        ("root/run/instance.traj", "root", "run"),
    ],
)
def test_extract_pred_trajectory_layout(tmp_path: Path, relative_path: str, run_name: str, instance_id: str) -> None:
    trajectory = tmp_path / relative_path
    trajectory.parent.mkdir(parents=True)
    submission = "example patch\n"
    trajectory.write_text(json.dumps({"info": {"submission": submission}}))

    main(["extract-pred", str(trajectory)])

    assert json.loads(trajectory.with_suffix(".pred").read_text()) == {
        "model_name_or_path": run_name,
        "model_patch": submission,
        "instance_id": instance_id,
    }
