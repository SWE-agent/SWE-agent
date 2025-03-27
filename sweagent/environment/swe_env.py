import asyncio
import logging
import shlex
from pathlib import PurePath
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field
from swerex.deployment.abstract import AbstractDeployment
from swerex.deployment.config import DeploymentConfig, DockerDeploymentConfig, get_deployment
from swerex.runtime.abstract import (
    BashAction,
    BashInterruptAction,
    CreateBashSessionRequest,
    ReadFileRequest,
    WriteFileRequest,
)
from swerex.runtime.abstract import Command as RexCommand

from sweagent.environment.hooks.abstract import CombinedEnvHooks, EnvHook
from sweagent.environment.repo import Repo, RepoConfig
from sweagent.utils.log import get_logger


class EnvironmentConfig(BaseModel):
    """Configure data sources and setup instructions for the environment in which we solve the tasks."""

    deployment: DeploymentConfig = Field(
        default_factory=lambda: DockerDeploymentConfig(image="python:3.11", python_standalone_dir="/root"),
        description="Deployment options.",
    )
    repo: RepoConfig | None = Field(
        default=None,
        description="Repository options.",
    )
    post_startup_commands: list[str] = []
    """Execute these commands before starting to run the agent but after all other setup steps.
    They will be executed in the same shell as the agent.
    Note: Every command is passed as a string, not a list of arguments.
    """
    post_startup_command_timeout: int = 500
    """Timeout for the post-startup commands.
    NOTE: The timeout applies to every command in `post_startup_commands` separately.
    """

    # pydantic config
    model_config = ConfigDict(extra="forbid")

    name: str = "main"


class SWEEnv:
    def __init__(
        self,
        *,
        deployment: AbstractDeployment,
        repo: Repo | RepoConfig | None,
        post_startup_commands: list[str],
        post_startup_command_timeout: int = 500,
        hooks: list[EnvHook] | None = None,
        name: str = "main",
    ):
        """This class represents the environment in which we solve the tasks.

        Args:
            deployment: SWE-ReX deployment instance
            repo: Repository configuration object, or anything following the `Repo` protocol
            post_startup_commands: Commands to execute before starting the agent
            hooks: Environment hooks (used to inject custom functionality)
                Equivalent to calling `add_hook` for each hook after initialization.
            name: Name of the environment
        """
        super().__init__()
        self.deployment = deployment
        self.repo = repo
        self._post_startup_commands = post_startup_commands
        self.post_startup_command_timeout = post_startup_command_timeout
        self.logger = get_logger("swea-env", emoji="���")
        self.name = name
        self.clean_multi_line_functions = lambda x: x
        self._chook = CombinedEnvHooks()
        for hook in hooks or []:
            self.add_hook(hook)

    @classmethod
    def from_config(cls, config: EnvironmentConfig) -> Self:
        """Create an environment instance from a configuration object.
        This is the recommended way to create an environment instance, unless you need
        more flexibility.
        """
        # Always copy config to avoid shared state between different instances
        config = config.model_copy(deep=True)
        return cls(
            deployment=get_deployment(config.deployment),
            repo=config.repo,
            post_startup_commands=config.post_startup_commands,
            post_startup_command_timeout=config.post_startup_command_timeout,
            name=config.name,
        )

    def add_hook(self, hook: EnvHook) -> None:
        """Add `EnvHook` to the environment.

        This allows to inject custom functionality at different stages of the environment
        lifecycle, in particular to connect SWE-agent to a new interface (like a GUI).
        """
        hook.on_init(env=self)
        self._chook.add_hook(hook)

    def start(self) -> None:
        """Start the environment and reset it to a clean state."""
        self._init_deployment()
        self.reset()
        for command in self._post_startup_commands:
            self.communicate(command, check="raise", timeout=self.post_startup_command_timeout)

    def _copy_repo(self) -> None:
        """Clone/copy repository/codebase in container"""
        if self.repo is None:
            return

        folders = self.communicate(input="ls", check="raise").split("\n")
        if self.repo.repo_name in folders:
            return

        self._chook.on_copy_repo_started(repo=self.repo)
        self.repo.copy(self.deployment)

    def hard_reset(self):
        """Resets the environment and deployment, i.e., completely restarts the
        deployment.
        """
        self.close()
        self.start()

    def reset(self):
        """Reset the environment to a clean state.
        Gets called by `start`, but can also be called independently to reset the
        environment to a clean state before a new attempt.

        Returns:
            observation: output from container
            info: additional information (e.g. debugging information)
        """
        self.communicate(input="cd /", check="raise")
        self._copy_repo()
        self._reset_repository()
        self._chook.on_environment_startup()

    def _reset_repository(self) -> None:
        """Clean repository of any modifications + Checkout base commit"""
        if self.repo is not None:
            self.logger.debug("Resetting repository %s to commit %s", self.repo.repo_name, self.repo.base_commit)
            # todo: Currently has swe-ft specific change: The original repo.copy isn't called, because the repo is already
            # present. However, reset --hard <BRANCH> also doesn't work. So modified it here to do a checkout instead.
            startup_commands = [
                f"cd /{self.repo.repo_name}",
                "export ROOT=$(pwd -P)",
                "git status",
                "git fetch",
                f"git checkout {self.repo.base_commit}",
                "git clean -fdxq",
            ]
            self.communicate(
                input=" && ".join(startup_commands),
                check="raise",
                error_msg="Failed to clean repository",
                # Sometimes this is slow because it rebuilds some index
                timeout=120,
            )

    def close(self) -> None:
        """Shutdown SWE-ReX deployment etc."""
        self.logger.info("Beginning environment shutdown...")
        asyncio.run(self.deployment.stop())
        self._chook.on_close()

    # MARK: Helper functions #

    def _init_deployment(
        self,
    ) -> None:
        """Handles container initialization. Defines container name and creates it.
        If cached_image is provided, it will use that image name instead of the default.
        """
        self._chook.on_start_deployment()
        asyncio.run(self.deployment.start())
        asyncio.run(self.deployment.runtime.create_session(CreateBashSessionRequest(startup_source=["/root/.bashrc"])))
        self.set_env_variables({"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"})
        self.logger.info("Environment Initialized")

    def interrupt_session(self):
        self.logger.info("Interrupting session")
        asyncio.run(self.deployment.runtime.run_in_session(BashInterruptAction()))

    # todo: return exit code?
    def communicate(
        self,
        input: str,
        timeout: int | float = 25,
        *,
        check: Literal["warn", "ignore", "raise"] = "ignore",
        error_msg: str = "Command failed",
    ) -> str:
        """Executes a command in the running shell. The details of this are handled by
        the SWE-ReX deployment/runtime.

        Args:
            input: input to send to container
            timeout_duration: duration to wait for output
            check: `ignore`: do not extract exit code (more stable), `warn`: extract exit code and log error if
                exit code is non-zero, `raise`: raise error if exit code is non-zero
            error_msg: error message to raise if the command fails

        Returns:
            output: output from container
        """
        self.logger.log(logging.TRACE, "Input:\n%s", input)  # type: ignore
        rex_check = "silent" if check else "ignore"
        r = asyncio.run(
            self.deployment.runtime.run_in_session(BashAction(command=input, timeout=timeout, check=rex_check))
        )
        output = r.output
        self.logger.log(logging.TRACE, "Output:\n%s", output)  # type: ignore
        if check != "ignore" and r.exit_code != 0:
            self.logger.error(f"{error_msg}:\n{output}")
            msg = f"Command {input!r} failed ({r.exit_code=}): {error_msg}"
            self.logger.error(msg)
            if check == "raise":
                self.close()
                raise RuntimeError(msg)
        return output

    def read_file(self, path: str | PurePath, encoding: str | None = None, errors: str | None = None) -> str:
        """Read file contents from container

        Args:
            path: Absolute path to file
            encoding: Encoding to use when reading the file. None means default encoding.
                This is the same as the `encoding` argument of `Path.read_text()`
            errors: Error handling to use when reading the file. None means default error handling.
                This is the same as the `errors` argument of `Path.read_text()`

        Returns:
            file_contents: Contents of file as string
        """
        r = asyncio.run(
            self.deployment.runtime.read_file(ReadFileRequest(path=str(path), encoding=encoding, errors=errors))
        )
        return r.content

    def write_file(self, path: str | PurePath, content: str) -> None:
        """Write content to file in container"""
        asyncio.run(self.deployment.runtime.write_file(WriteFileRequest(path=str(path), content=content)))

    def set_env_variables(self, env_variables: dict[str, str]) -> None:
        """Set environment variables in the environment."""
        if not env_variables:
            self.logger.debug("No environment variables to set")
            return
        _env_setters = [f"export {k}={shlex.quote(str(v))}" for k, v in env_variables.items()]
        command = " && ".join(_env_setters)
        self.communicate(command, check="raise")

    def execute_command(
        self,
        command: str,
        shell: bool = True,
        check: bool = False,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> None:
        """Execute a command in the environment independent of the session (i.e., as a subprocess)"""
        asyncio.run(
            self.deployment.runtime.execute(RexCommand(command=command, shell=shell, check=check, env=env, cwd=cwd))
        )
