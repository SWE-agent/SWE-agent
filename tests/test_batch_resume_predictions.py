import errno
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from sweagent.run.run import main
from sweagent.run.run_batch import RunBatch


def _prepare_batch(tmp_path: Path, instance_id: str, info: dict) -> tuple[list[str], Path]:
    instances = tmp_path / "instances.json"
    instances.write_text(
        json.dumps(
            [
                {
                    "env": {"deployment": {"type": "dummy"}},
                    "problem_statement": {"type": "text", "text": "A local batch task", "id": instance_id},
                }
            ]
        )
    )
    output = tmp_path / "output"
    trajectory = output / instance_id / f"{instance_id}.traj"
    trajectory.parent.mkdir(parents=True)
    trajectory.write_text(json.dumps({"info": info, "trajectory": [], "history": []}))
    args = [
        "run-batch",
        "--agent.model.name",
        "instant_empty_submit",
        "--instances.type",
        "expert_file",
        "--instances.path",
        str(instances),
        "--output_dir",
        str(output),
        "--raise_exceptions",
        "True",
    ]
    return args, trajectory


@pytest.mark.parametrize(
    ("previous", "submission", "instance_id"),
    [
        (None, "saved patch", "instance"),
        (b'{"model_patch": "', "saved \u03c0 patch", "instance"),
        (b"\xff", "", "group/nested"),
    ],
)
def test_run_batch_restores_prediction_on_resume(tmp_path, monkeypatch, previous, submission, instance_id):
    args, trajectory = _prepare_batch(tmp_path, instance_id, {"exit_status": "submitted", "submission": submission})
    prediction = trajectory.with_suffix(".pred")
    if previous is not None:
        prediction.write_bytes(previous)
    original_trajectory = trajectory.read_bytes()
    execute = Mock(side_effect=AssertionError("completed instances must not run again"))
    monkeypatch.setattr(RunBatch, "_run_instance", execute)

    main(args)
    main(args)

    execute.assert_not_called()
    assert trajectory.read_bytes() == original_trajectory
    expected = {"instance_id": instance_id, "model_name_or_path": "output", "model_patch": submission}
    assert json.loads(prediction.read_bytes()) == expected
    assert json.loads((tmp_path / "output" / "preds.json").read_bytes()) == {instance_id: expected}


def test_run_batch_keeps_existing_prediction(tmp_path, monkeypatch):
    args, trajectory = _prepare_batch(tmp_path, "instance", {"exit_status": "submitted", "submission": "original"})
    prediction = trajectory.with_suffix(".pred")
    existing = b'{ "instance_id": "instance", "model_patch": "replacement", "note": "custom metadata" }\n'
    prediction.write_bytes(existing)
    execute = Mock(side_effect=AssertionError("completed instances must not run again"))
    monkeypatch.setattr(RunBatch, "_run_instance", execute)

    main(args)

    execute.assert_not_called()
    assert prediction.read_bytes() == existing
    assert json.loads((tmp_path / "output" / "preds.json").read_bytes()) == {"instance": json.loads(existing)}


@pytest.mark.parametrize("info", [{"exit_status": "submitted"}, {"exit_status": "exit_cost", "submission": None}])
def test_run_batch_leaves_legacy_trajectory_without_submission_alone(tmp_path, monkeypatch, info):
    args, trajectory = _prepare_batch(tmp_path, "instance", info)
    original = trajectory.read_bytes()
    execute = Mock(side_effect=AssertionError("completed instances must not run again"))
    monkeypatch.setattr(RunBatch, "_run_instance", execute)

    main(args)

    execute.assert_not_called()
    assert trajectory.read_bytes() == original
    assert not trajectory.with_suffix(".pred").exists()


@pytest.mark.parametrize(("exit_status", "redo"), [("early_exit", False), ("submitted", True)])
def test_run_batch_still_runs_unfinished_or_explicitly_retried_instance(tmp_path, monkeypatch, exit_status, redo):
    args, trajectory = _prepare_batch(tmp_path, "instance", {"exit_status": exit_status, "submission": "old"})
    execute = Mock(side_effect=RuntimeError("would run the instance"))
    monkeypatch.setattr(RunBatch, "_run_instance", execute)
    if redo:
        args += ["--redo_existing", "True"]

    with pytest.raises(RuntimeError, match="would run the instance"):
        main(args)

    execute.assert_called_once()
    assert not trajectory.with_suffix(".pred").exists()
    assert trajectory.exists() is redo


@pytest.mark.parametrize("operation", ["read", "write"])
def test_run_batch_reports_prediction_io_error_and_keeps_trajectory(tmp_path, monkeypatch, operation):
    args, trajectory = _prepare_batch(tmp_path, "instance", {"exit_status": "submitted", "submission": "saved patch"})
    original = trajectory.read_bytes()
    prediction = trajectory.with_suffix(".pred")
    read_text = Path.read_text
    cleanup = Mock(side_effect=RunBatch._remove_instance_log_file_handlers)
    execute = Mock(side_effect=AssertionError("completed instances must not run again"))
    monkeypatch.setattr(RunBatch, "_run_instance", execute)
    monkeypatch.setattr(RunBatch, "_remove_instance_log_file_handlers", lambda runner, name: cleanup(runner, name))

    def fail_read(path, *args, **kwargs):
        if path == prediction:
            raise PermissionError(errno.EACCES, "cannot read prediction")
        return read_text(path, *args, **kwargs)

    if operation == "read":
        monkeypatch.setattr(Path, "read_text", fail_read)
        error = PermissionError(errno.EACCES, "cannot read prediction")
    else:
        error = OSError(errno.ENOSPC, "cannot write prediction")
        monkeypatch.setattr("sweagent.run.run_batch.save_predictions", Mock(side_effect=error))

    with pytest.raises(OSError) as caught:
        main(args)

    assert caught.value.errno == error.errno
    execute.assert_not_called()
    cleanup.assert_called_once()
    assert cleanup.call_args.args[1] == "instance"
    assert trajectory.read_bytes() == original
