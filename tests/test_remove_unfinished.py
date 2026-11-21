import json
from pathlib import Path

from sweagent.run.remove_unfinished import remove_unfinished

UNFINISHED = {"info": {"exit_status": "exit_error", "submission": None}}
FINISHED = {"info": {"exit_status": "submitted", "submission": "diff --git a/x b/x"}}


def _write_traj(base_dir: Path, instance_id: str, data: dict) -> Path:
    instance_dir = base_dir / instance_id
    instance_dir.mkdir(parents=True)
    (instance_dir / f"{instance_id}.traj").write_text(json.dumps(data), encoding="utf-8")
    return instance_dir


def test_remove_unfinished_does_not_depend_on_instance_id(tmp_path):
    """Unfinished instances are found by their trajectory, not by a `__` in the ID.

    Instance IDs are not necessarily SWE-bench style (`django__django-11099`): local
    problem statements use a hash and custom instances look like `task-1`.
    """
    for instance_id in ["django__django-11099", "task-1", "a4f3c1"]:
        _write_traj(tmp_path, instance_id, UNFINISHED)
    for instance_id in ["flask__flask-5015", "task-2"]:
        _write_traj(tmp_path, instance_id, FINISHED)
    (tmp_path / "not_an_instance").mkdir()

    remove_unfinished(tmp_path, dry_run=True)
    assert len(list(tmp_path.iterdir())) == 6

    remove_unfinished(tmp_path, dry_run=False)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["flask__flask-5015", "not_an_instance", "task-2"]
