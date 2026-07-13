from pathlib import Path
from unittest.mock import MagicMock

import pytest
from swerex.deployment.config import DummyDeploymentConfig

from sweagent.agent.agents import DefaultAgentConfig
from sweagent.agent.models import InstantEmptySubmitModelConfig
from sweagent.run.batch_instances import InstancesFromFile
from sweagent.run.common import BasicCLI
from sweagent.run.run import main
from sweagent.run.run_batch import RunBatch, RunBatchConfig
from sweagent.run.run_single import RunSingleConfig


def test_run_batch_config_snapshot_is_reusable(test_data_sources_path: Path, tmp_path: Path):
    config = RunBatchConfig(
        instances=InstancesFromFile(
            path=test_data_sources_path / "simple_instances.yaml",
            deployment=DummyDeploymentConfig(),
        ),
        agent=DefaultAgentConfig(model=InstantEmptySubmitModelConfig()),
        output_dir=tmp_path,
    )

    RunBatch.from_config(config)

    snapshot = tmp_path / "run_batch.config.yaml"
    loaded = BasicCLI(RunBatchConfig).get_config(["--config", str(snapshot)])
    assert loaded.model_dump(mode="json") == config.model_dump(mode="json")


def test_run_batch_instance_config_snapshot_is_reusable(
    test_data_sources_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    config = RunBatchConfig(
        instances=InstancesFromFile(
            path=test_data_sources_path / "simple_instances.yaml",
            deployment=DummyDeploymentConfig(),
        ),
        agent=DefaultAgentConfig(model=InstantEmptySubmitModelConfig()),
        output_dir=tmp_path,
    )
    run = RunBatch.from_config(config)
    instance = run.instances[0]
    expected = RunSingleConfig(
        agent=config.agent.model_copy(deep=True, update={"name": instance.problem_statement.id}),
        problem_statement=instance.problem_statement.model_copy(deep=True),
        env=instance.env.model_copy(deep=True),
    )
    monkeypatch.setattr("sweagent.run.run_batch.get_agent_from_config", lambda config: MagicMock())
    monkeypatch.setattr(run._progress_manager, "update_instance_status", lambda *args: None)

    def stop_before_environment_start(config):
        msg = "stop before environment start"
        raise RuntimeError(msg)

    monkeypatch.setattr("sweagent.run.run_batch.SWEEnv.from_config", stop_before_environment_start)

    with pytest.raises(RuntimeError, match="stop before environment start"):
        run._run_instance(instance)

    snapshot = tmp_path / instance.problem_statement.id / f"{instance.problem_statement.id}.config.yaml"
    loaded = BasicCLI(RunSingleConfig).get_config(["--config", str(snapshot)])
    assert loaded.model_dump(mode="json") == expected.model_dump(mode="json")


@pytest.mark.slow
def test_expert_instances(test_data_sources_path: Path, tmp_path: Path):
    ds_path = test_data_sources_path / "expert_instances.yaml"
    assert ds_path.exists()
    cmd = [
        "run-batch",
        "--agent.model.name",
        "instant_empty_submit",
        "--instances.type",
        "expert_file",
        "--instances.path",
        str(ds_path),
        "--output_dir",
        str(tmp_path),
        "--raise_exceptions",
        "True",
    ]
    main(cmd)
    for _id in ["simple_test_problem", "simple_test_problem_2"]:
        assert (tmp_path / f"{_id}" / f"{_id}.traj").exists(), list(tmp_path.iterdir())


@pytest.mark.slow
def test_simple_instances(test_data_sources_path: Path, tmp_path: Path):
    ds_path = test_data_sources_path / "simple_instances.yaml"
    assert ds_path.exists()
    cmd = [
        "run-batch",
        "--agent.model.name",
        "instant_empty_submit",
        "--instances.path",
        str(ds_path),
        "--output_dir",
        str(tmp_path),
        "--raise_exceptions",
        "True",
    ]
    main(cmd)
    assert (tmp_path / "simple_test_problem" / "simple_test_problem.traj").exists(), list(tmp_path.iterdir())


def test_empty_instances_simple(test_data_sources_path: Path, tmp_path: Path):
    ds_path = test_data_sources_path / "simple_instances.yaml"
    assert ds_path.exists()
    cmd = [
        "run-batch",
        "--agent.model.name",
        "instant_empty_submit",
        "--instances.path",
        str(ds_path),
        "--output_dir",
        str(tmp_path),
        "--raise_exceptions",
        "True",
        "--instances.filter",
        "doesnotmatch",
    ]
    with pytest.raises(ValueError, match="No instances to run"):
        main(cmd)


def test_empty_instances_expert(test_data_sources_path: Path, tmp_path: Path):
    ds_path = test_data_sources_path / "expert_instances.yaml"
    assert ds_path.exists()
    cmd = [
        "run-batch",
        "--agent.model.name",
        "instant_empty_submit",
        "--instances.path",
        str(ds_path),
        "--instances.type",
        "expert_file",
        "--output_dir",
        str(tmp_path),
        "--raise_exceptions",
        "True",
        "--instances.filter",
        "doesnotmatch",
    ]
    with pytest.raises(ValueError, match="No instances to run"):
        main(cmd)


# This doesn't work because we need to retrieve environment variables from the environment
# in order to format our templates.
# def test_run_batch_swe_bench_instances(tmp_path: Path):
#     cmd = [
#         "run-batch",
#         "--agent.model.name",
#         "instant_empty_submit",
#         "--instances.subset",
#         "lite",
#         "--instances.split",
#         "test",
#         "--instances.slice",
#         "0:1",
#         "--output_dir",
#         str(tmp_path),
#         "--raise_exceptions",
#         "--instances.deployment.type",
#         "dummy",
#     ]
#     main(cmd)
