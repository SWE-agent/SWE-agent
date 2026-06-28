"""Hook for saving agent trajectories to the launching environment's filesystem."""

import json
import threading
from pathlib import Path

from sweagent.agent.problem_statement import ProblemStatementConfig
from sweagent.environment.swe_env import SWEEnv
from sweagent.run.hooks.abstract import RunHook
from sweagent.types import AgentRunResult
from sweagent.utils.log import get_logger


class SaveTrajectoryHook(RunHook):
    """Saves agent trajectories to the launching environment's filesystem.

    For remote/cloud deployments the agent writes its ``.traj`` inside the
    container's ``output_dir``; only the patch is brought back to the launching
    environment via :class:`~sweagent.run.hooks.apply_patch.SaveApplyPatchHook`.
    This hook is the trajectory equivalent: it runs in the launching environment
    and persists the trajectory from the :class:`~sweagent.types.AgentRunResult`
    that ``on_instance_completed`` receives, so no remote access is required.

    The written document is ``{"trajectory": ..., "info": ...}``, i.e. the data
    that ``AgentRunResult`` exposes. This is intentionally a subset of the richer
    ``.traj`` that ``Agent.save_trajectory`` writes locally (which also includes
    ``history``, the environment name and the replay config), so it is not
    byte-identical to that file.
    """

    def __init__(self, pretty_print: bool = True):
        """Initialize the SaveTrajectoryHook.

        Args:
            pretty_print: If True, formats JSON with indentation for readability.
        """
        self.logger = get_logger("swea-save_trajectory", emoji="📝")
        self._pretty_print = pretty_print
        # Thread-local storage so that concurrent workers in run-batch do not
        # overwrite each other's per-instance state (_problem_statement).
        self._local = threading.local()

    def on_init(self, *, run):
        self._output_dir = Path(run.output_dir)

    def on_instance_start(self, *, index: int, env: SWEEnv, problem_statement: ProblemStatementConfig):
        self._local.problem_statement = problem_statement

    def on_instance_completed(self, *, result: AgentRunResult):
        problem_statement = getattr(self._local, "problem_statement", None)
        if problem_statement is None:
            self.logger.warning("No problem statement available, skipping trajectory save.")
            return
        self._save_trajectory(problem_statement.id, result)

    def _save_trajectory(self, instance_id: str, result: AgentRunResult) -> Path | None:
        """Save trajectory data to a ``.traj`` file.

        Returns:
            The path to the trajectory file, if it was saved. Otherwise, returns None.
        """
        trajectory_output_dir = self._output_dir / instance_id
        trajectory_output_dir.mkdir(exist_ok=True, parents=True)
        trajectory_output_file = trajectory_output_dir / f"{instance_id}.traj"
        trajectory_data = {"trajectory": result.trajectory, "info": result.info}
        indent = 2 if self._pretty_print else None
        trajectory_output_file.write_text(json.dumps(trajectory_data, indent=indent, ensure_ascii=False))
        self.logger.info(f"Saved trajectory with {len(result.trajectory)} steps to {trajectory_output_file}")
        return trajectory_output_file
