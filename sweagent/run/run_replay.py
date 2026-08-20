"""[cyan][bold]Replay a trajectory file.[/bold][/cyan]

[cyan][bold]=== DESCRIPTION ===[/bold][/cyan]

We will take all actions in the trajectory and execute them in an environment.

This has two main use cases:

1. Create a demo from a yaml file containing actions (can also be created from a trajectory file with [green]sweagent run traj-to-demo[/green]).
   [green]run-replay[/green] will execute the actions to get the environment output and produce a full trajectory to be used as a demo.
2. Debugging and testing of tools and environment behavior.

[cyan][bold]=== EXAMPLES ===[/bold][/cyan]

Replay a trajectory file:

[green]sweagent run replay --traj_path mytraj.traj[/green]

Replay a demo file:

[green]sweagent run replay --traj_path mydemo.demo.yaml[/green]
"""

import json
import sys
import tempfile
from getpass import getuser
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict
from swerex.deployment.abstract import AbstractDeployment
from swerex.deployment.config import DeploymentConfig, get_deployment
from typing_extensions import Self

from sweagent import TRAJECTORY_DIR
from sweagent.agent.agents import DefaultAgent
from sweagent.agent.models import ReplayModelConfig
from sweagent.environment.swe_env import SWEEnv
from sweagent.run.common import BasicCLI, ConfigHelper
from sweagent.run.run_single import RunSingle, RunSingleConfig
from sweagent.utils.config import load_environment_variables
from sweagent.utils.log import get_logger


class RunReplayConfig(BaseSettings, cli_implicit_flags=False):
    traj_path: Path
    deployment: DeploymentConfig | None = None
    """Override the deployment in the trajectory."""
    output_dir: Path = Path("DEFAULT")
    env_var_path: Path | None = None
    """Path to a .env file to load environment variables from."""
    update_config: list[Path] = []
    """Additional config files to merge with the replay config."""

    # pydantic config
    model_config = SettingsConfigDict(extra="forbid", env_prefix="SWE_AGENT_")

    def model_post_init(self, __context: Any) -> None:
        if self.output_dir == Path("DEFAULT"):
            user_id = getuser()
            self.output_dir = TRAJECTORY_DIR / user_id / f"replay___{self.traj_path.stem}"
        self.output_dir.mkdir(parents=True, exist_ok=True)


class RunReplay:
    def __init__(
        self,
        *,
        traj_path: Path,
        deployment: AbstractDeployment | None,
        output_dir: Path,
        update_config: list[Path] | None = None,
        _catch_errors: bool = False,
        _require_zero_exit_code: bool = False,
    ):
        self.traj_path = traj_path
        self.output_dir = output_dir
        self._replay_action_trajs_path = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        self.logger = get_logger("swea-run", emoji="🏃")
        self._catch_errors = _catch_errors
        self._require_zero_exit_code = _require_zero_exit_code
        self._update_config = update_config if update_config is not None else []

        if traj_path.suffix == ".yaml":
            self._traj_data = yaml.safe_load(traj_path.read_text())
        else:
            self._traj_data = json.loads(traj_path.read_text())
        self.config = self._get_config_from_agent(self._traj_data)

        if deployment is None:
            self.deployment = get_deployment(self.config.env.deployment)
        else:
            self.deployment = deployment

    def _get_config_from_agent(self, traj_data):
        try:
            if isinstance(traj_data["replay_config"], str):
                traj_data["replay_config"] = json.loads(traj_data["replay_config"])
            config = RunSingleConfig.model_validate(traj_data["replay_config"])
        except KeyError:
            msg = "Replay config not found in trajectory. Are you running on an old trajectory?"
            raise ValueError(msg)

        # Merge any additional config files
        for config_path in self._update_config:
            update_data = yaml.safe_load(config_path.read_text())
            # Store the current model config before merging
            current_model = config.agent.model
            # Convert the merged data back to a RunSingleConfig
            config_dict = config.model_dump(mode="json")
            merged_dict = config_dict | update_data

            # Ensure agent.model is preserved if not explicitly updated
            if "agent" in merged_dict and "model" not in merged_dict["agent"]:
                merged_dict["agent"]["model"] = current_model.model_dump(mode="json")

            config = RunSingleConfig.model_validate(merged_dict)

        config.agent.model = ReplayModelConfig(replay_path=self._replay_action_trajs_path)
        return config

    @property
    def instance_id(self) -> str:
        return Path(self.traj_path).stem

    @classmethod
    def from_config(cls, config: RunReplayConfig, **kwargs) -> Self:
        load_environment_variables(config.env_var_path)
        return cls(
            traj_path=config.traj_path,
            deployment=get_deployment(config.deployment) if config.deployment else None,
            output_dir=config.output_dir,
            update_config=config.update_config,
            **kwargs,
        )

    def _create_actions_file(self) -> None:
        # Verify config compatibility with tool calls
        has_tool_calls = any(
            "tool_calls" in item and item["tool_calls"] is not None
            for item in self._traj_data["history"]
            if item["role"] == "assistant"
        )

        agent_config = self.config.agent
        parse_function = agent_config.tools.parse_function.type
        use_function_calling = parse_function == "function_calling"

        if has_tool_calls and not use_function_calling:
            msg = (
                "Trajectory contains tool calls but config is not set up for function calling. "
                "Check that the config you want to use has agent.tools.parse_function.type set to 'function_calling'."
            )
            raise ValueError(msg)
        actions = []
        for ix, item in enumerate(self._traj_data["history"]):
            if item["role"] != "assistant":
                continue
            action = {"message": item["content"]}
            if use_function_calling:
                assert "tool_calls" in item and item["tool_calls"] is not None, (
                    f"Config is set to use `function_calling` but trajectory item {ix} is missing a tool call "
                    f"or has tool_calls set to None"
                )
                action["tool_calls"] = item["tool_calls"]
            actions.append(action)
        if len(actions) == 0:
            msg = "No actions found in trajectory"
            raise ValueError(msg)
        self._replay_action_trajs_path.write_text(json.dumps({self.instance_id: actions}))

    def _get_env(self) -> SWEEnv:
        return SWEEnv(
            deployment=self.deployment,
            repo=self.config.env.repo,
            post_startup_commands=[],
        )

    def _get_agent(self) -> DefaultAgent:
        agent = DefaultAgent.from_config(self.config.agent)
        agent._catch_errors = self._catch_errors
        agent._always_require_zero_exit_code = self._require_zero_exit_code
        return agent

    def _get_run_single(self) -> RunSingle:
        return RunSingle(
            self._get_env(),
            self._get_agent(),
            problem_statement=self.config.problem_statement,
            output_dir=Path(self.output_dir),
        )

    def main(self):
        self._create_actions_file()
        run_single = self._get_run_single()
        run_single.agent.replay_config = RunSingleConfig(
            agent=self.config.agent,
            problem_statement=run_single.problem_statement,
            env=self.config.env,
        )
        run_single.run()


def run_from_config(config: RunReplayConfig):
    RunReplay.from_config(config).main()


def run_from_cli(args: list[str] | None = None):
    if args is None:
        args = sys.argv[1:]
    help_text = (  # type: ignore
        __doc__ + "\n[cyan][bold]=== ALL THE OPTIONS ===[/bold][/cyan]\n\n" + ConfigHelper().get_help(RunReplayConfig)
    )
    run_from_config(BasicCLI(RunReplayConfig, help_text=help_text, default_settings=False).get_config(args))  # type: ignore


if __name__ == "__main__":
    run_from_cli()
