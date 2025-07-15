import subprocess
from pathlib import Path

import rich
import rich.markdown
import rich.panel

from sweagent.agent.problem_statement import ProblemStatementConfig
from sweagent.environment.repo import LocalRepoConfig
from sweagent.environment.swe_env import SWEEnv
from sweagent.run.common import _is_promising_patch
from sweagent.run.hooks.abstract import RunHook
from sweagent.types import AgentRunResult
from sweagent.utils.log import get_logger


class SaveApplyPatchHook(RunHook):
    """This hook saves patches to a separate directory and optionally applies them to a local repository."""

    def __init__(self, apply_patch_locally: bool = False, show_success_message: bool = True):
        self.logger = get_logger("swea-save_apply_patch", emoji="⚡️")
        self._apply_patch_locally = apply_patch_locally
        self._show_success_message = show_success_message

    def on_init(self, *, run):
        self._output_dir = Path(run.output_dir)

    def on_instance_start(self, *, index: int, env: SWEEnv, problem_statement: ProblemStatementConfig):
        self._env = env
        self._problem_statement = problem_statement

    def on_instance_completed(self, *, result: AgentRunResult):
        instance_id = self._problem_statement.id

        if self._is_file_submission(result.info):
            self.logger.info("Received file submission.")
            self._save_file_submission(instance_id, result.info)
            return

        patch_path = self._save_patch(instance_id, result.info)
        if patch_path:
            if not self._apply_patch_locally:
                return
            if not _is_promising_patch(result.info):
                return
            if self._env.repo is None:
                return
            if not isinstance(self._env.repo, LocalRepoConfig):
                return
            local_dir = Path(self._env.repo.path)
            self._apply_patch(patch_path, local_dir)

    @staticmethod
    def _print_patch_message(patch_output_file: Path):
        console = rich.console.Console()
        msg = [
            "SWE-agent has produced a patch that it believes will solve the issue you submitted!",
            "Use the code snippet below to inspect or apply it!",
        ]
        panel = rich.panel.Panel.fit(
            "\n".join(msg),
            title="🎉 Submission successful 🎉",
        )
        console.print(panel)
        content = [
            "```bash",
            "# The patch has been saved to your local filesystem at:",
            f"PATCH_FILE_PATH='{patch_output_file.resolve()}'",
            "# Inspect it:",
            'cat "${PATCH_FILE_PATH}"',
            "# Apply it to a local repository:",
            "cd <your local repo root>",
            'git apply "${PATCH_FILE_PATH}"',
            "```",
        ]
        console.print(rich.markdown.Markdown("\n".join(content)))

    def _is_file_submission(self, info) -> bool:
        """Check if the submission is a file."""
        if info.get("submission") is None:
            return False
        if isinstance(info["submission"], dict) and "file_name" in info["submission"]:
            return True
        return False

    def _save_file_submission(self, instance_id: str, info):
        """Save the file submission to the output directory."""
        file_info = info["submission"]
        file_name = file_info.get("file_name")
        if not file_name:
            self.logger.warning("No file name found in submission info.")
            return

        output_file_path = self._output_dir / instance_id / Path(file_name).name
        output_file_path.parent.mkdir(parents=True, exist_ok=True)
        if output_file_path.exists():
            self.logger.warning(f"File {output_file_path} already exists. Overwriting.")

        # Get the content of the file from the submission info
        file_content = file_info.get("file_content", "")
        if not file_content:
            self.logger.warning("No content found in submission info.")
            return

        output_file_path.write_text(file_content)
        self.logger.info(f"Saved file submission to {output_file_path}")

    def _save_patch(self, instance_id: str, info) -> Path | None:
        """Create patch files that can be applied with `git am`.

        Returns:
            The path to the patch file, if it was saved. Otherwise, returns None.
        """
        patch_output_dir = self._output_dir / instance_id
        patch_output_dir.mkdir(exist_ok=True, parents=True)
        patch_output_file = patch_output_dir / f"{instance_id}.patch"
        if info.get("submission") is None:
            self.logger.info("No patch to save.")
            return None
        model_patch = info["submission"]
        patch_output_file.write_text(model_patch)
        if _is_promising_patch(info):
            # Only print big congratulations if we actually believe
            # the patch will solve the issue
            if self._show_success_message:
                self._print_patch_message(patch_output_file)
        return patch_output_file

    def _apply_patch(self, patch_file: Path, local_dir: Path) -> None:
        """Apply a patch to a local directory."""

        assert local_dir.is_dir()
        assert patch_file.exists()
        # The resolve() is important, because we're gonna run the cmd
        # somewhere else
        cmd = ["git", "apply", str(patch_file.resolve())]
        try:
            subprocess.run(cmd, cwd=local_dir, check=True)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to apply patch {patch_file} to {local_dir}: {e}")
            return
        self.logger.info(f"Applied patch {patch_file} to {local_dir}")
