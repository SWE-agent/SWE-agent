"""SweBench evaluation hook.

Will be automatically added to `run_batch` if `SWEBenchInstances.evaluate` is set to true
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from threading import Lock
from time import time

from sweagent.run.hooks.abstract import RunHook
from sweagent.run.merge_predictions import merge_predictions
from sweagent.types import AgentRunResult
from sweagent.utils.log import get_logger


class SweBenchEvaluate(RunHook):
    _SUBSET_MAP = {"lite": "swe-bench_lite", "verified": "swe-bench_verified", "multimodal": "swe-bench_multimodal"}

    def __init__(self, output_dir: Path, subset: str, split: str, continuous_submission_every: int = 0) -> None:
        super().__init__()
        self.output_dir = output_dir
        self.subset = subset
        self.split = split
        self.continuous_submission_every = continuous_submission_every
        self.logger = get_logger("SB-evaluate", emoji="😬")
        self.merge_lock = Lock()
        self.last_evaluation_time = time()
        self.evaluation_interval = continuous_submission_every
        self._running_calls = []
        # We need to add a suffix to the run_id to avoid collisions when you reuse the name of your run
        self._time_suffix = datetime.now().strftime("%Y%m%d%H%M%S%f")

    @property
    def run_id(self) -> str:
        return f"{self.output_dir.name}_{self._time_suffix}"

    def _get_sb_call(self, preds_path: Path, submit_only: bool = False) -> list[str]:
        args = [
            "sb-cli",
            "submit",
            self._SUBSET_MAP[self.subset],
            self.split,
            "--predictions_path",
            str(preds_path),
            "--run_id",
            self.run_id,
            "--output_dir",
            str(self.output_dir / "sb-cli-reports"),
        ]
        if submit_only:
            args.extend(["--wait_for_evaluation", "0", "--gen_report", "0", "--verify_submission", "0"])
        return args

    def check_running_calls(self) -> None:
        """Warn if one of the running calls failed."""
        for call in self._running_calls:
            if call.poll() is not None:
                if call.returncode != 0:
                    self.logger.error("Failed to submit results to SweBench eval: %s", call.stderr.read())
                self._running_calls.remove(call)

    def on_instance_completed(self, *, result: AgentRunResult):
        if self.evaluation_interval == 0:
            return

        current_time = time()
        if current_time - self.last_evaluation_time < self.evaluation_interval:
            return

        with self.merge_lock:
            merge_predictions([self.output_dir], self.output_dir / "tmppreds.json")
            self.last_evaluation_time = current_time

        self._running_calls.append(
            subprocess.Popen(
                self._get_sb_call(preds_path=self.output_dir / "tmppreds.json", submit_only=True),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        )

    def move_sb_cli_report(self) -> None:
        """Move report from `sb-cli-reports` to `results.json`."""
        output_dir = self.output_dir / "sb-cli-reports"
        if not output_dir.exists():
            self.logger.warning("No SweBench report found at %s", output_dir)
            return
        (self.output_dir / "results.json").unlink(missing_ok=True)
        reports = list(output_dir.glob("*.json"))
        if len(reports) != 1:
            self.logger.warning("Expected 1 SweBench report at %s, found %d. Cannot rename.", output_dir, len(reports))
            return
        reports[0].rename(self.output_dir / "results.json")

    def on_end(self) -> None:
        self.logger.info("Submitting results to SWE-Bench")
        try:
            subprocess.run(
                self._get_sb_call(preds_path=self.output_dir / "preds.json"),
                check=True,
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
        except subprocess.CalledProcessError as e:
            self.logger.error("Failed to submit results to SweBench eval: %s", e)
        else:
            # remove temporary predictions if they exist
            if (self.output_dir / "tmppreds.json").exists():
                (self.output_dir / "tmppreds.json").unlink()
            self.move_sb_cli_report()
