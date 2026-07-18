import json
import threading
from pathlib import Path

from sweagent.agent.problem_statement import ProblemStatement, ProblemStatementConfig
from sweagent.environment.swe_env import SWEEnv
from sweagent.run.hooks.abstract import RunHook
from sweagent.types import AgentRunResult
from sweagent.utils.log import get_logger


class SaveTrajectoryHook(RunHook):
    """Save completed trajectories to the launcher-side output directory."""

    def __init__(self):
        self.logger = get_logger("swea-save_trajectory")
        # A single hook instance can be shared by multiple batch workers.
        self._local = threading.local()

    def on_init(self, *, run):
        self._output_dir = Path(run.output_dir)

    def on_instance_start(
        self, *, index: int, env: SWEEnv, problem_statement: ProblemStatement | ProblemStatementConfig
    ):
        self._local.problem_statement = problem_statement

    def on_instance_completed(self, *, result: AgentRunResult):
        instance_id = self._local.problem_statement.id
        trajectory_output_dir = self._output_dir / instance_id
        trajectory_output_dir.mkdir(exist_ok=True, parents=True)
        trajectory_output_file = trajectory_output_dir / f"{instance_id}.traj"
        trajectory_output_file.write_text(
            json.dumps(result.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        self.logger.info("Saved trajectory to %s", trajectory_output_file)
