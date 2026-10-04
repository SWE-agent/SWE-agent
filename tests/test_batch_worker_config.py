import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import MagicMock, patch

import yaml
from swerex.deployment.config import DummyDeploymentConfig

from sweagent.agent.agents import DefaultAgentConfig
from sweagent.agent.models import InstantEmptySubmitModelConfig
from sweagent.agent.problem_statement import TextProblemStatement
from sweagent.environment.swe_env import EnvironmentConfig
from sweagent.run.batch_instances import BatchInstance
from sweagent.run.run_batch import RunBatch
from sweagent.types import AgentRunResult


def test_parallel_workers_keep_instance_names_and_nested_config(tmp_path):
    shared = DefaultAgentConfig(model=InstantEmptySubmitModelConfig(), name="main")
    barrier = Barrier(2)
    configs = {}
    runner = RunBatch.__new__(RunBatch)
    runner.output_dir = tmp_path
    runner.agent_config = shared
    runner._progress_manager = MagicMock()
    runner._chooks = MagicMock()
    instances = [
        BatchInstance(
            env=EnvironmentConfig(deployment=DummyDeploymentConfig()),
            problem_statement=TextProblemStatement(text="task", id=i),
        )
        for i in ["first", "second"]
    ]

    def create_agent(config):
        configs[config.name] = config
        barrier.wait(timeout=10)
        agent = MagicMock()
        agent.run.return_value = AgentRunResult(info={"exit_status": "submitted"}, trajectory=[])
        return agent

    with (
        patch("sweagent.run.run_batch.get_agent_from_config", side_effect=create_agent),
        patch("sweagent.run.run_batch.SWEEnv.from_config", side_effect=lambda _: MagicMock()),
    ):
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(runner._run_instance, instances))
    assert shared.name == "main"
    assert set(configs) == {"first", "second"}
    for instance_id, config in configs.items():
        assert config.name == instance_id
        assert config is not shared
        assert config.model is not shared.model
        snapshot = yaml.safe_load((tmp_path / instance_id / f"{instance_id}.config.yaml").read_text())
        if isinstance(snapshot, str):
            snapshot = json.loads(snapshot)
        assert snapshot["agent"]["name"] == instance_id
