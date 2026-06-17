"""
This module contains the configuration for the tools that are made available to the agent.

The `ToolConfig` class is used to configure the tools that are available to the agent.
The `ToolHandler` class is used to handle the tools that are available to the agent.
"""

import asyncio
import json
import os
import re
import shlex
from functools import cached_property
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from swerex.runtime.abstract import Command as RexCommand
from swerex.runtime.abstract import UploadRequest
from typing_extensions import Self

from sweagent.environment.swe_env import SWEEnv
from sweagent.tools.bundle import Bundle
from sweagent.tools.commands import BASH_COMMAND, Command
from sweagent.tools.parsing import FunctionCallingParser, JsonParser, ParseFunction
from sweagent.tools.utils import _guard_multiline_input, generate_command_docs
from sweagent.utils.log import get_logger


class ToolFilterConfig(BaseModel):
    """Filter out commands that are blocked by the environment
    (for example interactive commands like `vim`).
    """

    blocklist_error_template: str = "Operation '{{action}}' is not supported by this environment."
    """The error template to use when a command is blocked."""

    blocklist: list[str] = [
        "vim",
        "vi",
        "emacs",
        "nano",
        "nohup",
        "gdb",
        "less",
        "tail -f",
        "python -m venv",
        "make",
    ]
    """Block any command that starts with one of these"""

    blocklist_standalone: list[str] = [
        "python",
        "python3",
        "ipython",
        "bash",
        "sh",
        "/bin/bash",
        "/bin/sh",
        "nohup",
        "vi",
        "vim",
        "emacs",
        "nano",
        "su",
    ]
    """Block any command that matches one of these exactly"""

    block_unless_regex: dict[str, str] = {
        "radare2": r"\b(?:radare2)\b.*\s+-c\s+.*",
        "r2": r"\b(?:radare2)\b.*\s+-c\s+.*",
    }
    """Block any command that matches one of these names unless it also matches the regex"""


class ToolConfig(BaseModel):
    """Configuration for the tools that are made available to the agent."""

    filter: ToolFilterConfig = ToolFilterConfig()
    """Filter out commands that are blocked by the environment
    (for example interactive commands like `vim`).
    """

    bundles: list[Bundle] = Field(default_factory=list)
    """The tool bundles to load."""

    propagate_env_variables: list[str] = []
    """Environment variables to propagate to the environment.
    This is useful if you want to propagate API keys or similar from your own environment to the
    environment in which the tools run.
    IMPORTANT NOTE: The value of the environment variables can be read in debug log files,
    so be careful with your API keys!
    """

    env_variables: dict[str, Any] = {
        "PAGER": "cat",
        "MANPAGER": "cat",
        "LESS": "-R",
        "PIP_PROGRESS_BAR": "off",
        "TQDM_DISABLE": "1",
        "GIT_PAGER": "cat",
    }
    """Shorthand to set environment variables for the tools, effectively
    equivalent to adding `export VARNAME=value` to the `reset_commands`.
    """

    registry_variables: dict[str, Any] = {}
    """Populate the registry with these variables. Will be written out as json in the registry file."""

    submit_command: str = "submit"
    """The command/tool to use to submit the solution."""

    parse_function: ParseFunction = Field(default_factory=FunctionCallingParser)
    """The action parser that is responsible for parsing the model output into a thought and action.
    """

    enable_bash_tool: bool = True
    """Whether to enable the bash tool in addition to the other tools specified in bundles."""

    format_error_template: str = None  # type: ignore
    """Defaults to format_error_template in ParseFunction"""

    command_docs: str = None  # type: ignore
    """Automatically generated documentation generated based on
    the loaded tool bundles.
    """

    multi_line_command_endings: dict[str, str] = {}
    submit_command_end_name: str | None = None

    """Commands to install dependencies and tools.
    These commands are executed in a subprocess and are not part of the environment state.
    """

    reset_commands: list[str | list[str]] = []
    """Commands to reset the environment. They will also be called when we start the environment.
    Unlike `install_commands`, these commands are part of the environment state.
    """

    execution_timeout: int = 30
    """Timeout for executing commands in the environment"""

    install_timeout: int = 300
    """Timeout used for each of the installation commands"""

    total_execution_timeout: int = 1800
    """Timeout for executing all commands in the environment.
    Note: Does not interrupt running commands, but will stop the agent for the next step.
    """

    max_consecutive_execution_timeouts: int = 3
    """Maximum number of consecutive execution timeouts before the agent exits.
    """

    @cached_property
    def use_function_calling(self) -> bool:
        return isinstance(self.parse_function, FunctionCallingParser)

    @cached_property
    def state_commands(self) -> list[str]:
        """This property returns the state commands from all bundles.
        State commands are commands that are used to get the state of the environment
        (e.g., the current working directory).
        """
        return [bundle.state_command for bundle in self.bundles if bundle.state_command]

    # todo: move to ToolHandler?
    @cached_property
    def commands(self) -> list[Command]:
        """Read command files and return parsed command objects"""
        commands = []
        tool_sources: dict[str, Path] = {}  # Track which file each tool comes from
        # Add bash command if enabled
        if self.enable_bash_tool:
            commands.append(BASH_COMMAND)
            tool_sources[BASH_COMMAND.name] = Path("<builtin>")

        # Collect commands from all bundles
        for bundle in self.bundles:
            for command in bundle.commands:
                if command.name in tool_sources:
                    existing_source = tool_sources[command.name]
                    msg = (
                        f"Tool '{command.name}' is defined multiple times:\n"
                        f"  - First definition in: {existing_source}\n"
                        f"  - Duplicate definition in: {bundle.path}"
                    )
                    raise ValueError(msg)
                commands.append(command)
                tool_sources[command.name] = bundle.path

        return commands

    @cached_property
    def tools(self) -> list[dict]:
        return [command.get_function_calling_tool() for command in self.commands]

    # todo: can some of these be moved to ToolHandler?
    def model_post_init(self, __context):
        # for caching:
        commands = self.commands
        multi_line_command_endings = {
            command.name: command.end_name for command in commands if command.end_name is not None
        }
        self.tools

        # assert not self.enable_bash_tool and parse_function is FunctionCallingParser or JsonParser
        if not self.enable_bash_tool and not (
            isinstance(self.parse_function, FunctionCallingParser) or isinstance(self.parse_function, JsonParser)
        ):
            msg = f"Bash tool can only be disabled if {FunctionCallingParser.type} parser or {JsonParser.type} parser is used."
            raise ValueError(msg)

        self.multi_line_command_endings = multi_line_command_endings
        self.command_docs = generate_command_docs(
            self.commands,
            [],
            **self.env_variables,
        )
        if self.format_error_template is None:
            self.format_error_template = self.parse_function.format_error_template
        for command in commands:
            if command.name == self.submit_command:
                self.submit_command_end_name = command.end_name
                break


# Shell control operators that separate one command invocation from another in a
# compound command line. Used to make the blocklist see every individual command,
# not just the first token of the whole line.
_COMMAND_SEPARATOR_TOKENS = frozenset({";", "&", "&&", "|", "||", "\n", "(", ")", "{", "}"})
# Tokens produced by quote-aware tokenization of ``$(...)`` that are not real commands.
_SUBSTITUTION_NOISE_TOKENS = frozenset({"$", "(", ")"})
# Inner commands of command substitutions ``$(...)`` and back-ticked ``...``.
_COMMAND_SUBSTITUTION_RE = re.compile(r"\$\((.*?)\)|`(.*?)`", re.DOTALL)
# Wrapper programs that run another command passed as their (trailing) argument.
# e.g. ``env vim``, ``sudo nano`` -- the wrapped command must also be checked.
_COMMAND_WRAPPERS = frozenset(
    {"env", "command", "builtin", "exec", "nohup", "sudo", "time", "nice", "stdbuf", "setsid"}
)
_ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _iter_command_invocations(action: str) -> list[str]:
    """Break a (possibly compound) command line into its individual command invocations.

    Splits on shell control operators (``;`` ``&&`` ``||`` ``|`` ``&`` newlines) and
    additionally extracts the inner commands of command substitutions (``$(...)`` and
    back-ticks) so that e.g. ``true; vim``, ``echo x | less`` and ``$(vim)`` each surface
    the ``vim``/``less`` invocation. Tokenization is quote-aware so operators inside a
    quoted argument (``echo "a && vim"``) do not spuriously split the line.

    Best-effort, lexical-only: this is used to harden a reliability filter (the
    interactive-command blocklist), not as a security sandbox.
    """
    invocations: list[str] = []
    # Recurse into command substitutions first; their inner commands are real
    # invocations that the shell will run.
    for match in _COMMAND_SUBSTITUTION_RE.finditer(action):
        inner = match.group(1) if match.group(1) is not None else match.group(2)
        if inner and inner.strip():
            invocations.extend(_iter_command_invocations(inner))

    # Quote-aware tokenization: operators become their own tokens, but operators that
    # appear inside quotes stay part of the argument they belong to.
    lexer = shlex.shlex(action, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        # Unbalanced quotes etc. -- fall back to the raw, naive operator split so we
        # still surface the obvious invocations.
        tokens = None
    if tokens is None:
        for segment in re.split(r"\|\||&&|\||;|&|\n", action):
            segment = segment.strip()
            if segment:
                invocations.append(segment)
        return invocations

    current: list[str] = []
    for token in tokens:
        if token in _COMMAND_SEPARATOR_TOKENS:
            if current:
                invocations.append(" ".join(current))
                current = []
            continue
        if token in _SUBSTITUTION_NOISE_TOKENS:
            # Leftover ``$`` / ``(`` / ``)`` from a substitution we already handled above.
            continue
        current.append(token)
    if current:
        invocations.append(" ".join(current))
    return invocations


def _normalize_invocation(segment: str) -> str:
    """Return ``segment`` with leading env-var assignments / wrapper programs removed and
    the executable reduced to its basename.

    e.g. ``/usr/bin/vim file`` -> ``vim file``, ``env FOO=bar vim`` -> ``vim``,
    ``sudo nano /etc/hosts`` -> ``nano /etc/hosts``. Whitespace-normalized so that
    prefix checks (``startswith``) and exact checks behave the same as on a plain
    invocation. Returns the original (stripped) segment if it cannot be tokenized.
    """
    try:
        tokens = shlex.split(segment)
    except ValueError:
        # Unbalanced quotes etc. -- fall back to a naive split so we still try to match.
        tokens = segment.split()
    index = 0
    # Skip leading ``VAR=value`` environment assignments.
    while index < len(tokens) and _ENV_ASSIGNMENT_RE.match(tokens[index]):
        index += 1
    # Skip wrapper programs (and their options / inline env assignments) so the wrapped
    # command becomes the head, e.g. ``env -i FOO=bar vim`` -> ``vim``.
    while index < len(tokens) and tokens[index] in _COMMAND_WRAPPERS:
        index += 1
        while index < len(tokens) and (tokens[index].startswith("-") or _ENV_ASSIGNMENT_RE.match(tokens[index])):
            index += 1
    if index >= len(tokens):
        return segment.strip()
    # Reduce the executable to its basename so path-qualified forms (``/usr/bin/vim``)
    # match the same way bare names do.
    tokens = tokens[index:]
    tokens[0] = tokens[0].rsplit("/", 1)[-1]
    return " ".join(tokens)


class ToolHandler:
    def __init__(self, tools: ToolConfig):
        """This class handles most of the tool usage. It has the following responsibilities:

        - Install the tools
        - Parse commands and handle multiline commands
        - Decide if an action should be blocked
        - Get the current state of the environment
        """
        # Always copy config to avoid shared state between different instances across threads
        self.config = tools.model_copy(deep=True)
        # partially initialized in `install_commands`.
        self._reset_commands = []
        self._command_patterns = self._get_command_patterns()
        self.logger = get_logger("swea-tools", emoji="🧰")
        # For testing: Return this state instead of querying the environment
        self.mock_state: dict[str, str] | None = None

    @classmethod
    def from_config(cls, config: ToolConfig) -> Self:
        return cls(config)

    # Installation & Reset
    # --------------------

    def install(self, env: SWEEnv) -> None:
        self._install_commands(env)
        self.reset(env)

    def reset(self, env: SWEEnv) -> None:
        self.logger.info("Resetting tools")
        env_variables = self.config.env_variables.copy() | {
            var: os.getenv(var) for var in self.config.propagate_env_variables
        }
        env.set_env_variables(env_variables)
        env.write_file("/root/.swe-agent-env", json.dumps(self.config.registry_variables))
        env.write_file("/root/state.json", "{}")
        env.communicate(" && ".join(self._reset_commands), check="raise", timeout=self.config.install_timeout)

    async def _upload_bundles(self, env: SWEEnv) -> None:
        await asyncio.gather(
            *(
                env.deployment.runtime.upload(
                    UploadRequest(source_path=bundle.path.as_posix(), target_path=f"/root/tools/{bundle.path.name}")
                )
                for bundle in self.config.bundles
            )
        )

    async def _is_command_available(self, env, command: str, env_vars: dict[str, str]) -> None:
        if command == "bash":
            return
        try:
            await env.deployment.runtime.execute(
                RexCommand(command=f"which {command}", shell=True, check=True, env=env_vars)
            )
        except Exception:
            msg = f"Tool {command} is not available in the container."
            raise RuntimeError(msg) from None

    async def _check_available_commands(self, env: SWEEnv, env_vars: dict[str, str]) -> None:
        await asyncio.gather(
            *(self._is_command_available(env, command.name, env_vars) for command in self.config.commands)
        )

    def _install_commands(self, env: SWEEnv) -> None:
        """Make sure all commands are available in the container"""
        env.set_env_variables(self.config.env_variables)
        cwd = env.communicate("pwd", check="raise").strip()
        asyncio.run(self._upload_bundles(env))
        for bundle in self.config.bundles:
            cmds = [
                f"export PATH=/root/tools/{bundle.path.name}/bin:$PATH",
                f"chmod +x /root/tools/{bundle.path.name}/bin/*",
            ]
            if (bundle.path / "install.sh").exists():
                cmds.append(f"cd /root/tools/{bundle.path.name} && source install.sh")
            cmds.append(f"chmod +x /root/tools/{bundle.path.name}/bin/*")
            env.communicate(
                " && ".join(cmds),
                check="raise",
                timeout=self.config.install_timeout,
            )
        env.communicate(f"cd {cwd}", check="raise")
        path = env.communicate("echo $PATH", check="raise").strip()
        asyncio.run(self._check_available_commands(env, {"PATH": path}))

    # Getting state
    # -------------

    def _get_state(self, env: SWEEnv) -> dict[str, str]:
        """Retrieve the state from the environment"""
        try:
            state_str = env.read_file("/root/state.json")
        except FileNotFoundError:
            self.logger.warning("State file not found, returning empty state")
            return {}
        if not state_str.strip():
            self.logger.warning("State file is empty, returning empty state")
            return {}
        try:
            state = json.loads(state_str)
        except json.JSONDecodeError as e:
            msg = f"State {state_str!r} is not valid json. This is an internal error, please report it."
            raise ValueError(msg) from e
        if not isinstance(state, dict):
            msg = f"State commands must return a dictionary. Got {state!r} instead."
            raise ValueError(msg)
        return state

    def get_state(self, env: SWEEnv) -> dict[str, str]:
        """Execute state commands from all bundles and combine their results.
        This can be used to extract environment variables etc. from the environment.
        """
        if self.mock_state is not None:
            return self.mock_state

        for state_command in self.config.state_commands:
            env.communicate(state_command, check="warn")
        combined_state = self._get_state(env)
        self.logger.debug(f"Retrieved state from environment: {combined_state}")
        return combined_state

    # Blocking
    # --------

    def should_block_action(self, action: str) -> bool:
        """Check if the command should be blocked.

        The blocklist is a reliability filter that keeps the agent from launching
        interactive/long-running programs (``vim``, ``less``, ``tail -f``, a bare
        ``python`` REPL, ...) that would otherwise hang the run loop. To make the
        decision consistent with what the shell actually executes, every individual
        command in a compound command line is examined -- not just the first token --
        and each is checked both as written and in a normalized form (path prefix and
        ``env``/``sudo``-style wrappers stripped, executable reduced to its basename).
        This closes lexical bypasses such as ``/usr/bin/vim``, ``env vim`` and
        ``true; vim`` that the previous first-token-only check missed.
        """
        action = action.strip()
        if not action:
            return False
        # The whole, original action is still checked first for backward compatibility
        # with multi-word blocklist entries (e.g. "tail -f", "python -m venv").
        candidates = [action]
        for invocation in _iter_command_invocations(action):
            candidates.append(invocation)
            normalized = _normalize_invocation(invocation)
            if normalized and normalized != invocation:
                candidates.append(normalized)
        for candidate in candidates:
            if self._is_blocked_invocation(candidate):
                return True
        return False

    def _is_blocked_invocation(self, candidate: str) -> bool:
        """Apply the configured blocklist rules to a single command string."""
        candidate = candidate.strip()
        if not candidate:
            return False
        if any(candidate.startswith(f) for f in self.config.filter.blocklist):
            return True
        if candidate in self.config.filter.blocklist_standalone:
            return True
        name = candidate.split()[0]
        if name in self.config.filter.block_unless_regex and not re.search(
            self.config.filter.block_unless_regex[name], candidate
        ):
            return True
        return False

    # Parsing & multiline commands
    # -----------------------------

    def check_for_submission_cmd(self, output: str) -> bool:
        """Function for checking submission request."""
        if r"<<SWE_AGENT_SUBMISSION>>" in output:
            return True
        return False

    def parse_actions(self, output: dict) -> tuple[str, str]:
        """Parse the model output into a thought and action."""
        return self.config.parse_function(output, self.config.commands)

    def guard_multiline_input(self, action: str) -> str:
        """Split action by multiline commands, then append the first line in each multiline command with "<< '{end_name}'".
        Multiline commands (which are specified by an end_name) are commands that span multiple lines and are terminated by a specific end_name.

        Their multi-line argument is sent using a heredoc, which is a way to send a multi-line string to a command in bash.
        """
        return _guard_multiline_input(action, self._get_first_multiline_cmd)

    def _get_first_multiline_cmd(self, action: str) -> re.Match | None:
        """Return the first match of a command pattern in the action string.
        Where first match is defined by the start of the match.

        The match object has three groups: (1) command name, (2) command arguments, (3) end name
        """
        patterns = {
            k: v
            for k, v in self._command_patterns.items()
            if k in self.config.multi_line_command_endings or k == self.config.submit_command
        }
        matches = list()
        for _, pat in patterns.items():
            match = pat.search(action)
            if match:
                matches.append(match)
        if len(matches) == 0:
            return None
        matches = sorted(matches, key=lambda x: x.start())
        return matches[0]

    def _get_command_patterns(self) -> dict[str, re.Pattern]:
        """Creates regular expressions for the commands"""

        _command_patterns = {}
        for command in self.config.commands:
            if command.end_name is not None:
                pat = re.compile(
                    rf"^\s*({command.name})\s*(.*?)^({command.end_name})\s*$",
                    re.DOTALL | re.MULTILINE,
                )
                _command_patterns[command.name] = pat
            else:
                pat = re.compile(rf"^\s*({command.name})\s*(.*?)$", re.MULTILINE)
                _command_patterns[command.name] = pat
        submit_pat = re.compile(
            rf"^\s*({self.config.submit_command})\s*(.*?)^({self.config.submit_command_end_name})\s*$",
            re.DOTALL | re.MULTILINE,
        )
        _command_patterns[self.config.submit_command] = submit_pat
        return _command_patterns
