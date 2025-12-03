"""[cyan][bold]Run SWE-agent on a single instance taken from github or similar.[/bold][/cyan]

[cyan][bold]=== BASIC OPTIONS ===[/bold][/cyan]

  -h --help           Show help text and exit
  --help_option      Print specific help text and exit
  --config CONFIG     Load additional config files. Use this option multiple times to load
                      multiple files, e.g., --config config1.yaml --config config2.yaml

[cyan][bold]=== EXAMPLES ===[/bold][/cyan]

Basic usage: Run over a [bold][cyan]github issue[/bold][/cyan][green]:

sweagent run --config config/default.yaml --agent.model.name "gpt-4o" \\
    --env.repo.github_url=https://github.com/SWE-agent/test-repo/ \\
    --problem_statement.github_url=https://github.com/SWE-agent/test-repo/issues/1
[/green]

By default this will start a docker container and run the agent in there.
You can set the image with [green]--env.docker.image[/green].

Here's an example that uses [bold][cyan]modal[/bold][/cyan] instead of docker and also a [bold][cyan]local repository[/bold][/cyan]:

[green]sweagent run --config config/default.yaml --agent.model.name "gpt-4o" \\
    --env.deployment.type=modal --env.repo.path /path/to/repo \\
    --problem_statement.path=path/to/problem_statement.md
[/green]
"""

import getpass
import sys
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from sweagent.agent.agents import AbstractAgent, AgentConfig, get_agent_from_config
from sweagent.agent.problem_statement import (
    EmptyProblemStatement,
    ProblemStatement,
    ProblemStatementConfig,
)
from sweagent.environment.swe_env import EnvironmentConfig, SWEEnv
from sweagent.run.common import AutoCorrectSuggestion as ACS
from sweagent.run.common import BasicCLI, ConfigHelper, save_predictions
from sweagent.run.hooks.abstract import CombinedRunHooks, RunHook
from sweagent.run.hooks.apply_patch import SaveApplyPatchHook
from sweagent.run.hooks.open_pr import OpenPRConfig, OpenPRHook
from sweagent.utils.config import load_environment_variables
from sweagent.utils.log import add_file_handler, get_logger


class RunSingleActionConfig(BaseModel):
    """Run real-life actions (opening PRs, etc.) if we can solve the issue."""

    # Open a PR with the patch if we can solve the issue
    open_pr: bool = False
    pr_config: OpenPRConfig = Field(default_factory=OpenPRConfig)
    # When working with local repository: Apply patch
    apply_patch_locally: bool = False

    # pydantic config
    model_config = ConfigDict(extra="forbid")


def _get_default_output_dir(output_dir: Path, problem_statement: ProblemStatement, agent: AgentConfig) -> Path:
    if output_dir == Path("DEFAULT"):
        user_id = getpass.getuser()
        problem_id = problem_statement.id
        try:
            model_id = agent.model.id  # type: ignore[attr-defined]
        except AttributeError:
            model_id = "unknown_model"
        config_file = getattr(agent, "_config_files", ["no_config"])[0]
        if isinstance(config_file, Path):
            config_file = config_file.stem
        return Path.cwd() / "trajectories" / user_id / f"{config_file}__{model_id}___{problem_id}"
    return output_dir


class RunSingleConfig(BaseSettings, cli_implicit_flags=False):
    env: EnvironmentConfig = Field(default_factory=EnvironmentConfig, description="Environment options.")
    agent: AgentConfig = Field(description="Agent options.")
    problem_statement: ProblemStatementConfig = Field(
        default_factory=EmptyProblemStatement, description="Problem statement options."
    )
    output_dir: Path = Field(default=Path("DEFAULT"), description="Output directory.")

    actions: RunSingleActionConfig = Field(default_factory=RunSingleActionConfig)

    env_var_path: Path | None = None
    """Path to a .env file to load environment variables from."""

    # pydantic config
    model_config = SettingsConfigDict(extra="forbid", env_prefix="SWE_AGENT_")

    def set_default_output_dir(self) -> None:
        # Needs to be called explicitly, because self._config_files will be setup
        # post-init.
        self.output_dir = _get_default_output_dir(self.output_dir, self.problem_statement, self.agent)

    @classmethod
    def _get_auto_correct(cls) -> list[ACS]:
        return [
            ACS("model", "agent.model.name"),
            ACS("agent.model", "agent.model.name"),
            ACS("model.name", "agent.model.name"),
            ACS("per_instance_cost_limit", "agent.model.per_instance_cost_limit"),
            ACS("model.per_instance_cost_limit", "agent.model.per_instance_cost_limit"),
            ACS("config_file", "config"),
            ACS(
                "data_path",
                help="--data_path is no longer support for SWE-A 1.0. Please check the tutorial and use one of the --problem_statement options, e.g., --problem_statement.github_url or --problem_statement.path",
            ),
            ACS(
                "repo_path",
                help="--repo_path is no longer support for SWE-A 1.0. Please check the tutorial and use one of the --env.repo options, e.g., --env.repo.github_url or --env.repo.path",
            ),
            ACS("repo.path", "env.repo.path"),
        ]


class RunSingle:
    def __init__(
        self,
        env: SWEEnv,
        agent: AbstractAgent,
        problem_statement: ProblemStatement | ProblemStatementConfig,
        *,
        output_dir: Path = Path("."),
        hooks: list[RunHook] | None = None,
        actions: RunSingleActionConfig | None = None,
    ):
        """Note: When initializing this class, make sure to add the hooks that are required by your actions.
        See `from_config` for an example.
        """
        self.logger = get_logger("swea-run", emoji="🏃")
        instance_id = problem_statement.id
        _log_filename_template = f"{instance_id}.{{level}}.log"
        for level in ["trace", "debug", "info"]:
            add_file_handler(
                output_dir / instance_id / _log_filename_template.format(level=level),
                level=level,
                id_=f"{instance_id}-{level}",
            )
        self.env = env
        self.agent = agent
        self.output_dir = output_dir
        self._hooks = []
        if actions is not None:
            actions = RunSingleActionConfig()
        self.actions = actions
        self._chooks = CombinedRunHooks()
        self.problem_statement = problem_statement
        for hook in hooks or []:
            self.add_hook(hook)

    @property
    def hooks(self) -> list[RunHook]:
        return self._chooks.hooks

    @classmethod
    def from_config(cls, config: RunSingleConfig) -> Self:
        load_environment_variables(config.env_var_path)
        config.set_default_output_dir()
        config.output_dir.mkdir(parents=True, exist_ok=True)
        agent = get_agent_from_config(config.agent)
        agent.replay_config = config  # type: ignore[attr-defined]
        self = cls(
            env=SWEEnv.from_config(config.env),
            agent=agent,
            problem_statement=config.problem_statement,
            output_dir=config.output_dir,
            actions=config.actions,
        )
        self.add_hook(SaveApplyPatchHook(apply_patch_locally=config.actions.apply_patch_locally))
        if config.actions.open_pr:
            self.logger.debug("Adding OpenPRHook")
            self.add_hook(OpenPRHook(config.actions.pr_config))
        return self

    def add_hook(self, hook: RunHook) -> None:
        hook.on_init(run=self)
        self._chooks.add_hook(hook)

    def run(self):
        self._chooks.on_start()
        self.logger.info("Starting environment")
        self.env.start()
        self.logger.info("Running agent")
        self._chooks.on_instance_start(index=0, env=self.env, problem_statement=self.problem_statement)
        output_dir = self.output_dir / self.problem_statement.id
        output_dir.mkdir(parents=True, exist_ok=True)
        if self.agent.replay_config is not None:  # type: ignore[attr-defined]
            (output_dir / "config.yaml").write_text(yaml.dump(self.agent.replay_config.model_dump_json(), indent=2))  # type: ignore[attr-defined]
        result = self.agent.run(
            problem_statement=self.problem_statement,
            env=self.env,
            output_dir=output_dir,
        )
        self._chooks.on_instance_completed(result=result)
        self.logger.info("Done")
        self._chooks.on_end()
        save_predictions(self.output_dir, self.problem_statement.id, result)
        self.env.close()


def run_from_config(config: RunSingleConfig):
    RunSingle.from_config(config).run()


def run_from_cli(args: list[str] | None = None):
    if args is None:
        args = sys.argv[1:]
    assert __doc__ is not None
    help_text = (  # type: ignore
        __doc__ + "\n[cyan][bold]=== ALL THE OPTIONS ===[/bold][/cyan]\n\n" + ConfigHelper().get_help(RunSingleConfig)
    )
    run_from_config(BasicCLI(RunSingleConfig, help_text=help_text).get_config(args))  # type: ignore


if __name__ == "__main__":
    run_from_cli()
