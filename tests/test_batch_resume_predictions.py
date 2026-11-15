import errno
import json
import stat
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from sweagent.run.common import save_recovered_prediction
from sweagent.run.merge_predictions import merge_predictions
from sweagent.run.run import main
from sweagent.run.run_batch import RunBatch


def _prepare_batch(
    tmp_path: Path, instance_id: str, info: dict, *, raise_exceptions: bool = True
) -> tuple[list[str], Path]:
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
        str(raise_exceptions),
    ]
    return args, trajectory


@pytest.mark.parametrize(
    ("previous", "submission", "instance_id"),
    [
        (None, "saved patch", "instance"),
        (b'{"model_patch": "', "saved \u03c0 patch", "instance"),
        (b"\xff", "", "group/nested"),
        (None, None, "empty-submission"),
    ],
)
def test_run_batch_restores_prediction_on_resume(tmp_path, monkeypatch, previous, submission, instance_id):
    args, trajectory = _prepare_batch(tmp_path, instance_id, {"exit_status": "submitted", "submission": submission})
    prediction = trajectory.with_suffix(".pred")
    if previous is not None:
        prediction.write_bytes(previous)
        prediction.chmod(0o640)
        original_mode = stat.S_IMODE(prediction.stat().st_mode)
    original_trajectory = trajectory.read_bytes()
    execute = Mock(side_effect=AssertionError("completed instances must not run again"))
    monkeypatch.setattr(RunBatch, "_run_instance", execute)

    main(args)
    main(args)

    execute.assert_not_called()
    assert trajectory.read_bytes() == original_trajectory
    expected = {"instance_id": instance_id, "model_name_or_path": "output", "model_patch": submission}
    assert json.loads(prediction.read_bytes()) == expected
    if previous is not None:
        assert stat.S_IMODE(prediction.stat().st_mode) == original_mode
    assert json.loads((tmp_path / "output" / "preds.json").read_bytes()) == {
        instance_id: {**expected, "model_patch": submission if submission is not None else ""}
    }


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


def test_run_batch_leaves_legacy_trajectory_without_submission_alone(tmp_path, monkeypatch):
    args, trajectory = _prepare_batch(tmp_path, "instance", {"exit_status": "submitted"})
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
        prediction.write_text(json.dumps({"instance_id": "instance", "model_patch": "previous"}))
        monkeypatch.setattr(Path, "read_text", fail_read)
        error = PermissionError(errno.EACCES, "cannot read prediction")
    else:
        error = OSError(errno.ENOSPC, "cannot write prediction")
        monkeypatch.setattr("sweagent.run.common.save_recovered_prediction", Mock(side_effect=error))

    with pytest.raises(OSError) as caught:
        main(args)

    assert caught.value.errno == error.errno
    execute.assert_not_called()
    cleanup.assert_called_once()
    assert cleanup.call_args.args[1] == "instance"
    assert trajectory.read_bytes() == original
    report = yaml.safe_load((tmp_path / "output" / "run_batch_exit_statuses.yaml").read_text())
    assert report["instances_by_exit_status"] == {f"Uncaught {type(error).__name__}": ["instance"]}


def test_run_batch_continues_after_failed_prediction_recovery(tmp_path, monkeypatch):
    args, blocked = _prepare_batch(
        tmp_path, "blocked", {"exit_status": "submitted", "submission": "saved patch"}, raise_exceptions=False
    )
    instances = tmp_path / "instances.json"
    data = json.loads(instances.read_bytes())
    data.append({**data[0], "problem_statement": {**data[0]["problem_statement"], "id": "other"}})
    instances.write_text(json.dumps(data))
    output = tmp_path / "output"
    other = output / "other" / "other.traj"
    other.parent.mkdir()
    other.write_bytes(blocked.read_bytes())
    original = blocked.read_bytes()
    execute = Mock(side_effect=AssertionError("completed instances must not run again"))
    monkeypatch.setattr(RunBatch, "_run_instance", execute)

    def fail_blocked_prediction(path, model_name_or_path, instance_id, submission):
        if instance_id == "blocked":
            raise OSError(errno.ENOSPC, "cannot write prediction")
        save_recovered_prediction(path, model_name_or_path, instance_id, submission)

    monkeypatch.setattr("sweagent.run.common.save_recovered_prediction", fail_blocked_prediction)

    main(args)

    execute.assert_not_called()
    assert blocked.read_bytes() == original
    assert not blocked.with_suffix(".pred").exists()
    assert json.loads((output / "preds.json").read_bytes()) == {
        "other": {"instance_id": "other", "model_name_or_path": "output", "model_patch": "saved patch"}
    }
    report = yaml.safe_load((output / "run_batch_exit_statuses.yaml").read_text())
    assert report["instances_by_exit_status"] == {"Uncaught OSError": ["blocked"], "skipped (submitted)": ["other"]}


def test_run_batch_stages_prediction_out_of_view_of_merge(tmp_path, monkeypatch):
    args, trajectory = _prepare_batch(tmp_path, "resumed", {"exit_status": "submitted", "submission": "saved patch"})
    output = tmp_path / "output"
    existing = output / "other" / "other.pred"
    existing.parent.mkdir()
    other_prediction = {"instance_id": "other", "model_patch": "other patch"}
    existing.write_text(json.dumps(other_prediction))
    read_during_write = tmp_path / "during-write.json"
    write_text = Path.write_text
    execute = Mock(side_effect=AssertionError("completed instances must not run again"))
    monkeypatch.setattr(RunBatch, "_run_instance", execute)

    def observe_partial_write(path, contents, *args, **kwargs):
        if path.is_relative_to(trajectory.parent) and '"model_patch": "saved patch"' in contents:
            write_text(path, contents[:1], *args, **kwargs)
            merge_predictions([output], read_during_write)
        return write_text(path, contents, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", observe_partial_write)
    main(args)

    execute.assert_not_called()
    assert json.loads(read_during_write.read_bytes()) == {"other": other_prediction}
    assert json.loads(trajectory.with_suffix(".pred").read_bytes())["model_patch"] == "saved patch"


def test_run_batch_cleans_partial_staging_after_write_failure(tmp_path, monkeypatch):
    args, trajectory = _prepare_batch(tmp_path, "resumed", {"exit_status": "submitted", "submission": "saved patch"})
    prediction = trajectory.with_suffix(".pred")
    previous = b'{"model_patch": "'
    prediction.write_bytes(previous)
    original = trajectory.read_bytes()
    write_text = Path.write_text
    interrupted_write = []
    execute = Mock(side_effect=AssertionError("completed instances must not run again"))
    monkeypatch.setattr(RunBatch, "_run_instance", execute)

    def interrupt_prediction_write(path, contents, *args, **kwargs):
        if '"model_patch": "saved patch"' in contents:
            interrupted_write.append(path)
            write_text(path, contents[:1], *args, **kwargs)
            raise OSError(errno.ENOSPC, "cannot complete prediction")
        return write_text(path, contents, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", interrupt_prediction_write)

    with pytest.raises(OSError, match="cannot complete prediction"):
        main(args)

    execute.assert_not_called()
    assert len(interrupted_write) == 1
    assert not interrupted_write[0].parent.exists()
    assert prediction.read_bytes() == previous
    assert trajectory.read_bytes() == original
