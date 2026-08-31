import re
from collections.abc import Callable
from typing import Any

from sweagent.tools.commands import Command


def _guard_multiline_input(action: str, match_fct: Callable[[str], re.Match | None]) -> str:
    """Split action by multiline commands, then append the first line in each multiline command with "<< '{end_name}'".
    Multiline commands (which are specified by an end_name) are commands that span multiple lines and are terminated by a specific end_name.

    Their multi-line argument is sent using a heredoc, which is a way to send a multi-line string to a command in bash.
    """
    parsed_action = []
    rem_action = action
    while rem_action.strip():
        first_match = match_fct(rem_action)
        if first_match:
            pre_action = rem_action[: first_match.start()]
            match_action = rem_action[first_match.start() : first_match.end()]
            rem_action = rem_action[first_match.end() :]
            if pre_action.strip():
                parsed_action.append(pre_action)
            if match_action.strip():
                eof = first_match.group(3).strip()
                if not match_action.split("\n")[0].strip().endswith(f"<< '{eof}'"):
                    guarded_command = match_action
                    first_line = guarded_command.split("\n")[0]
                    guarded_command = guarded_command.replace(first_line, first_line + f" << '{eof}'", 1)
                    parsed_action.append(guarded_command)
                else:
                    parsed_action.append(match_action)
        else:
            parsed_action.append(rem_action)
            rem_action = ""
    return "\n".join(parsed_action)


def _should_quote(value: Any, command: Command) -> bool:
    """Returns True if the value should be quoted, False otherwise."""
    if command.name == "bash":
        return False
    return isinstance(value, str) and command.end_name is None


def get_signature(cmd):
    """Generate a command signature from its arguments.

    Args:
        cmd: Command object to generate signature for

    Returns:
        Formatted signature string
    """
    signature = cmd.name
    if "arguments" in cmd.__dict__ and cmd.arguments is not None:
        if cmd.end_name is None:
            for argument in cmd.arguments:
                param = argument.name
                if argument.required:
                    signature += f" <{param}>"
                else:
                    signature += f" [<{param}>]"
        else:
            for argument in cmd.arguments[:-1]:
                param = argument.name
                if argument.required:
                    signature += f" <{param}>"
                else:
                    signature += f" [<{param}>]"
            signature += f"\n{list(cmd.arguments[-1].keys())[0]}\n{cmd.end_name}"
    return signature


def generate_command_docs(
    commands: list[Command],
    subroutine_types,
    **kwargs,
) -> str:
    """Generate detailed command documentation.

    Format includes docstring, signature and argument details.

    Args:
        commands: List of commands to document
        subroutine_types: List of subroutines to document
        **kwargs: Additional format variables for docstrings

    Returns:
        Formatted documentation string
    """
    docs = ""
    for cmd in commands + subroutine_types:
        docs += f"{cmd.name}:\n"
        if cmd.docstring is not None:
            docs += f"  docstring: {cmd.docstring.format(**kwargs)}\n"
        if cmd.signature is not None:
            docs += f"  signature: {cmd.signature}\n"
        else:
            docs += f"  signature: {get_signature(cmd)}\n"
        if cmd.arguments:
            docs += "  arguments:\n"
            for argument in cmd.arguments:
                param = argument.name
                req_string = "required" if argument.required else "optional"
                docs += f"    - {param} ({argument.type}) [{req_string}]: {argument.description}\n"
        docs += "\n"
    return docs
