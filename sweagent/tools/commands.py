"""
Core module for defining and parsing commands in the SWE Agent system.

This module provides the foundational classes and utilities for defining commands that can be executed by the agent.
It is used extensively by:

- tools.py: For command installation, execution and environment management
- parsing.py: For parsing model outputs into executable commands
- utils.py: For handling multi-line commands and argument quoting

Key Classes:
- Command: Represents an executable command with arguments and documentation
- Argument: Defines an argument that can be passed to a command

The module supports both simple bash commands and complex multi-line commands with typed arguments.
Commands can be defined either in bash scripts with YAML docstrings or as bash functions.
"""

from __future__ import annotations

import re
import string
from collections import Counter
from functools import cached_property

from pydantic import BaseModel, field_validator, model_validator

from sweagent.utils.jinja_warnings import _warn_probably_wrong_jinja_syntax

ARGUMENT_NAME_PATTERN = r"[a-zA-Z_][a-zA-Z0-9_-]*"


def _extract_keys(format_string: str) -> set[str]:
    """Given a format string, returns a set of all the keys in the format string.

    Used for validating that command signatures match their argument definitions.

    Args:
        format_string: A Python format string containing named fields

    Returns:
        Set of field names found in the format string
    """
    formatter = string.Formatter()
    keys = set()
    for _, field_name, _, _ in formatter.parse(format_string):
        if field_name is not None:
            keys.add(field_name)
    return keys


class Argument(BaseModel):
    f"""Defines an argument that can be passed to a command.

    Attributes:
        name: The argument name, must match {ARGUMENT_NAME_PATTERN!r}
        type: The argument type (e.g. "string", "integer")
        description: Human readable description of the argument
        required: Whether this argument must be provided
        enum: Optional list of allowed values
        argument_format: Format string for how to render the argument value in the command
    """

    name: str
    type: str
    items: dict[str, str] | None = None
    description: str
    required: bool
    enum: list[str] | None = None
    argument_format: str = "{{value}}"
    """How to invoke the argument in the command. Make sure to use jinja syntax ({{value}}) instead of {value})."""

    @field_validator("argument_format")
    def validate_argument_format(cls, value: str) -> str:
        _warn_probably_wrong_jinja_syntax(value)
        return value


class Command(BaseModel):
    """Represents an executable command with arguments and documentation.

    A command can be either a simple bash command or a multi-line command terminated by an end marker.

    Attributes:
        name: The command name
        docstring: Human readable description of what the command does
        signature: Optional custom signature override
        end_name: For multi-line commands, the terminating marker
        arguments: List of arguments accepted by the command

    Properties:
        invoke_format: Format string for constructing the full command invocation
    """

    name: str
    docstring: str | None
    signature: str | None = None
    # if there is an end_name, then it is a multi-line command
    end_name: str | None = None
    arguments: list[Argument] = []

    @cached_property
    def invoke_format(self) -> str:
        """Gets the format string for invoking this command with arguments.

        Returns either the custom signature with argument placeholders replaced,
        or a default format of "command arg1 arg2 ...".
        """
        if self.signature:
            # First validate that all arguments are present in the original signature
            for arg in self.arguments:
                if not (
                    f"<{arg.name}>" in self.signature
                    or f"[<{arg.name}>]" in self.signature
                    or f"{{{arg.name}}}" in self.signature
                    or f"--{arg.name}" in self.signature
                ):
                    msg = (
                        f"Missing argument {arg.name} in signature: {self.signature}. Did you format the signature correctly? "
                        f"You must include all argument names in the signature with <{arg.name}>, [<{arg.name}>], {{{arg.name}}}, or --{arg.name} notation."
                    )
                    raise ValueError(msg)

            # Then do the replacement
            return re.sub(rf"\[?<({ARGUMENT_NAME_PATTERN})>\]?", r"{\1}", self.signature)
        else:
            # cmd arg_format_1 arg_format_2 ...
            _invoke_format = f"{self.name} "
            for arg in self.arguments:
                _invoke_format += f"{{{arg.name}}} "
            return _invoke_format

    def get_function_calling_tool(self) -> dict:
        """Converts this command into an OpenAI function calling tool definition.

        Returns:
            Dict containing the OpenAI function schema for this command
        """
        tool = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.docstring or "",
            },
        }
        properties = {}
        required = []
        if self.arguments:
            for arg in self.arguments:
                properties[arg.name] = {"type": arg.type, "description": arg.description}

                if arg.items:
                    properties[arg.name]["items"] = arg.items

                if arg.required:
                    required.append(arg.name)

                # Handle enum if present
                if arg.enum:
                    properties[arg.name]["enum"] = arg.enum
        tool["function"]["parameters"] = {"type": "object", "properties": properties, "required": required}
        return tool

    @model_validator(mode="after")
    def validate_arguments(self) -> Command:
        """Validates command argument configuration.

        Checks:
        - Required arguments come before optional ones
        - Argument names are unique
        - Argument names match the pattern
        - Arguments match the signature

        Returns:
            The validated Command instance

        Raises:
            ValueError: If validation fails
        """
        if not self.arguments:
            return self
        found_optional = False
        for arg in self.arguments:
            if found_optional and arg.required:
                msg = f"Command '{self.name}': Required argument '{arg.name}' cannot come after optional arguments"
                raise ValueError(msg)
            if not arg.required:
                found_optional = True

        name_counts = Counter(arg.name for arg in self.arguments)
        duplicates = {name for name, count in name_counts.items() if count > 1}
        if duplicates:
            msg = f"Command '{self.name}': Duplicate argument names: {duplicates}"
            raise ValueError(msg)
        for arg in self.arguments:
            if not re.match(ARGUMENT_NAME_PATTERN, arg.name):
                msg = f"Command '{self.name}': Invalid argument name: '{arg.name}'"
                raise ValueError(msg)
        if (invoke_keys := _extract_keys(self.invoke_format)) != {arg.name for arg in self.arguments}:
            msg = f"Command '{self.name}': Argument names ({invoke_keys}) in signature / invoke_format {self.invoke_format!r} do not match argument names"
            raise ValueError(msg)
        return self


# Default Bash tool
BASH_COMMAND = Command(
    name="bash",
    # name="execute_bash",
    signature="<command>",
    # signature="echo '<command>'\n<command>\necho \"root@workspace:${{PWD}} #\n[Command finished with exit code ${{?}}]\"",
    docstring="runs the given command directly in bash",
    arguments=[
        Argument(
            name="command",
            type="string",
            description="The bash command to execute.",
            required=True,
        )
    ],
)
