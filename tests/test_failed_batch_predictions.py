import json
from unittest.mock import MagicMock, patch

import pytest
from swerex.deployment.config import DummyDeploymentConfig

from sweagent.agent.problem_statement import TextProblemStatement
from sweagent.environment.swe_env import EnvironmentConfig
from sweagent.exceptions import ModelConfigurationError
from sweagent.run.batch_instances import BatchInstance
from sweagent.run.merge_predictions import merge_predictions
from sweagent.run.run_batch import RunBatch, _BreakLoop


@pytest.mark.parametrize(
    ("error", "raise_exceptions", "expected"),
    [
        (RuntimeError("deployment failed"), False, None),
        (RuntimeError("deployment failed"), True, RuntimeError),
        (ModelConfigurationError("bad model"), False, _BreakLoop),
        (KeyboardInterrupt(), False, _BreakLoop),
    ],
)
def test_failed_attempt_writes_empty_prediction(tmp_path, error, raise_exceptions, expected):
    runner = RunBatch.__new__(RunBatch)
    runner.logger = MagicMock()
    runner.output_dir = tmp_path
    runner._num_workers = 1
    runner._raise_exceptions = raise_exceptions
    runner._progress_manager = MagicMock()
    runner._progress_manager.n_completed = 1
    runner._run_instance = MagicMock(side_effect=error)
    runner.should_skip = MagicMock(return_value=False)
    runner._add_instance_log_file_handlers = MagicMock()
    runner._remove_instance_log_file_handlers = MagicMock()
    instance = BatchInstance(
        env=EnvironmentConfig(deployment=DummyDeploymentConfig()),
        problem_statement=TextProblemStatement(text="task", id="failed"),
    )
    pred_path = tmp_path / "failed" / "failed.pred"
    pred_path.parent.mkdir()
    pred_path.write_text(json.dumps({"instance_id": "failed", "model_patch": "stale patch"}))
    with patch("sweagent.run.run_batch.register_thread_name"):
        if expected is None:
            runner.run_instance(instance)
        else:
            with pytest.raises(expected):
                runner.run_instance(instance)
    assert json.loads(pred_path.read_text())["model_patch"] == ""
    merge_predictions([tmp_path])
    assert json.loads((tmp_path / "preds.json").read_text())["failed"]["model_patch"] == ""
    runner._remove_instance_log_file_handlers.assert_called_once_with("failed")


@pytest.mark.parametrize("skip", [True, False])
def test_existing_prediction_is_preserved_when_skipped_or_run_succeeds(tmp_path, skip):
    runner = RunBatch.__new__(RunBatch)
    runner.logger = MagicMock()
    runner.output_dir = tmp_path
    runner._num_workers = 1
    runner._raise_exceptions = False
    runner._progress_manager = MagicMock()
    runner._progress_manager.n_completed = 1
    runner.should_skip = MagicMock(return_value="submitted" if skip else False)
    runner._add_instance_log_file_handlers = MagicMock()
    runner._remove_instance_log_file_handlers = MagicMock()
    instance = BatchInstance(
        env=EnvironmentConfig(deployment=DummyDeploymentConfig()),
        problem_statement=TextProblemStatement(text="task", id="finished"),
    )
    pred_path = tmp_path / "finished" / "finished.pred"
    pred_path.parent.mkdir()
    pred_path.write_text(json.dumps({"instance_id": "finished", "model_patch": "valid patch"}))

    def run_instance(_):
        from sweagent.run.common import save_predictions
        from sweagent.types import AgentRunResult

        result = AgentRunResult(info={"submission": "valid patch", "exit_status": "submitted"}, trajectory=[])
        save_predictions(tmp_path, "finished", result)
        return result

    runner._run_instance = MagicMock(side_effect=run_instance)
    with patch("sweagent.run.run_batch.register_thread_name"):
        runner.run_instance(instance)
    assert json.loads(pred_path.read_text())["model_patch"] == "valid patch"
    assert runner._run_instance.call_count == (0 if skip else 1)
