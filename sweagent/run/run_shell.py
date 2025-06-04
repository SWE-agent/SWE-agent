"""[cyan][bold]Run SWE-agent in semi-interactive mode.[/bold][/cyan]

[cyan][bold]sweagen-sh is EXPERIMENTAL[/bold][/cyan]

[cyan][bold]=== BASIC OPTIONS ===[/bold][/cyan]

  -h --help           Show help text and exit
  --help_option      Print specific help text and exit
  --config CONFIG     Load additional config files. Use this option multiple times to load
                      multiple files, e.g., --config config1.yaml --config config2.yaml

"""

import argparse
from pathlib import Path

import yaml
from swerex.deployment.config import DockerDeploymentConfig

from sweagent import CONFIG_DIR
from sweagent.agent.agents import AbstractAgent, ShellAgentConfig
from sweagent.agent.extra.shell_agent import ShellAgent
from sweagent.agent.problem_statement import (
    EmptyProblemStatement,
    ProblemStatement,
    ProblemStatementConfig,
)
from sweagent.environment.repo import PreExistingRepoConfig
from sweagent.environment.swe_env import EnvironmentConfig, SWEEnv
from sweagent.run.common import save_predictions
from sweagent.run.hooks.abstract import CombinedRunHooks, RunHook
from sweagent.run.run_single import _get_default_output_dir
from sweagent.utils.config import load_environment_variables
from sweagent.utils.log import add_file_handler, get_logger


class RunShell:
    def __init__(
        self,
        env: SWEEnv,
        agent: AbstractAgent,
        problem_statement: ProblemStatement | ProblemStatementConfig,
        *,
        output_dir: Path = Path("."),
        hooks: list[RunHook] | None = None,
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
        self._chooks = CombinedRunHooks()
        self.problem_statement = problem_statement
        for hook in hooks or []:
            self.add_hook(hook)

    @property
    def hooks(self) -> list[RunHook]:
        return self._chooks.hooks

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


def get_cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(dest="repo", type=Path, help="Path to the repository.")
    # parser.add_argument(dest="--model", type=str, help="Model to use.", default="claude-sonnet-4-20250514")
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to the agent config file.",
        default=CONFIG_DIR / "exotic" / "default_shell.yaml",
    )
    return parser


def run_from_cli(args: list[str] | None = None):
    cli_args = get_cli().parse_args(args)
    try:
        load_environment_variables(Path(".env"))
    except FileNotFoundError:
        print("Env file .env not found, please set API key as env variables.")
    env_config = EnvironmentConfig(
        repo=PreExistingRepoConfig(repo_name="repo", reset=False),
        deployment=DockerDeploymentConfig(
            image="python:3.11",
            docker_args=[
                "-v",
                f"{cli_args.repo}:/repo",
            ],
        ),
    )
    agent_config = ShellAgentConfig.model_validate(yaml.safe_load(cli_args.config.read_text())["agent"])
    agent = ShellAgent.from_config(agent_config)
    env = SWEEnv.from_config(env_config)
    run_shell = RunShell(
        env,
        agent,
        problem_statement=EmptyProblemStatement(),
        output_dir=_get_default_output_dir(cli_args.repo, EmptyProblemStatement(), agent_config),
    )
    run_shell.run()


if __name__ == "__main__":
    run_from_cli()
