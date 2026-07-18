from __future__ import annotations

import pytest
from jinja2 import Template

from sweagent.exceptions import FormatError, FunctionCallingFormatError
from sweagent.tools.commands import Argument, Command
from sweagent.tools.parsing import (
    ActionParser,
    EditFormat,
    FunctionCallingParser,
    Identity,
    JsonParser,
    ThoughtActionParser,
    XMLFunctionCallingParser,
    XMLThoughtActionParser,
)


def test_action_parser():
    parser = ActionParser()
    command = Command(name="ls", docstring="")
    thought, action = parser({"message": "ls -l"}, [command])
    assert thought == "ls -l"
    assert action == "ls -l"
    with pytest.raises(FormatError):
        parser({"message": "invalid command"}, [command])


def test_thought_action_parser():
    parser = ThoughtActionParser()
    model_response = "Let's look at the files in the current directory.\n```\nls -l\n```"
    thought, action = parser({"message": model_response}, [])
    assert thought == "Let's look at the files in the current directory.\n"
    assert action == "ls -l\n"
    with pytest.raises(FormatError):
        parser({"message": "No code block"}, [])


def test_xml_thought_action_parser():
    parser = XMLThoughtActionParser()
    model_response = "Let's look at the files in the current directory.\n<command>\nls -l\n</command>"
    thought, action = parser({"message": model_response}, [])
    assert thought == "Let's look at the files in the current directory."
    assert action == "ls -l"
    with pytest.raises(FormatError):
        parser({"message": "No command tags"}, [])


def test_edit_format_parser():
    parser = EditFormat()
    model_response = "Let's replace the contents.\n```\nimport os\nos.listdir()\n```"
    thought, action = parser({"message": model_response}, [])
    assert thought == "Let's replace the contents.\n"
    assert action == "import os\nos.listdir()\n"
    with pytest.raises(FormatError):
        parser({"message": "No code block"}, [])


def test_identity_parser():
    parser = Identity()
    model_response = "Return as is"
    thought, action = parser({"message": model_response}, [])
    assert thought == model_response
    assert action == model_response


def test_json_parser():
    parser = JsonParser()
    model_response = '{"thought": "List files", "command": {"name": "ls", "arguments": {"path": "."}}}'
    thought, action = parser({"message": model_response}, [])
    assert thought == "List files"
    assert action == "ls ."

    invalid_json = "Not a JSON"
    with pytest.raises(FormatError):
        parser({"message": invalid_json}, [])

    missing_keys = '{"thought": "Missing command key"}'
    with pytest.raises(FormatError):
        parser({"message": missing_keys}, [])


def test_function_calling_parser():
    parser = FunctionCallingParser()
    command = Command(name="ls", docstring="", arguments=[])

    # Test successful parsing
    model_response = {
        "message": "Let's list the files",
        "tool_calls": [{"function": {"name": "ls", "arguments": "{}"}}],
    }
    thought, action = parser(model_response, [command])
    assert thought == "Let's list the files"
    assert action == "ls"

    # Test with missing tool_calls
    with pytest.raises(FormatError):
        parser({"message": "No tool calls"}, [command])

    # Test with multiple tool calls
    multiple_calls = {
        "message": "Multiple calls",
        "tool_calls": [
            {"function": {"name": "ls", "arguments": "{}"}},
            {"function": {"name": "cd", "arguments": "{}"}},
        ],
    }
    with pytest.raises(FormatError):
        parser(multiple_calls, [command])

    # Test with invalid command
    invalid_command = {
        "message": "Invalid command",
        "tool_calls": [{"function": {"name": "invalid", "arguments": "{}"}}],
    }
    with pytest.raises(FormatError):
        parser(invalid_command, [command])

    # Test with invalid JSON arguments
    invalid_json = {
        "message": "Invalid JSON",
        "tool_calls": [{"function": {"name": "ls", "arguments": "invalid json"}}],
    }
    with pytest.raises(FormatError):
        parser(invalid_json, [command])


def test_function_calling_parser_error_message():
    template = Template(FunctionCallingParser().error_message)
    exc1 = FunctionCallingFormatError("test", "missing")
    assert "did not use any tool calls" in template.render(**exc1.extra_info, exception_message=exc1.message)


def _str_replace_editor_command() -> Command:
    return Command(
        name="str_replace_editor",
        signature="str_replace_editor <command> <path> [<view_range>] [<old_str>]",
        docstring="Custom editing tool",
        arguments=[
            Argument(
                name="command",
                type="string",
                description="The command to run.",
                required=True,
            ),
            Argument(
                name="path",
                type="string",
                description="Path to file or directory.",
                required=True,
            ),
            Argument(
                name="view_range",
                type="array",
                items={"type": "integer"},
                description="Line range to view.",
                required=False,
                argument_format="--view_range {{value|join(' ')}}",
            ),
            Argument(
                name="old_str",
                type="string",
                description="String to replace.",
                required=False,
                argument_format="--old_str {{value}}",
            ),
        ],
    )


def test_function_calling_parser_preserves_array_arguments():
    parser = FunctionCallingParser()
    command = _str_replace_editor_command()
    model_response = {
        "message": "View the relevant lines",
        "tool_calls": [
            {
                "function": {
                    "name": "str_replace_editor",
                    "arguments": '{"command": "view", "path": "/testbed/file.py", "view_range": [1, 50]}',
                }
            }
        ],
    }

    thought, action = parser(model_response, [command])

    assert thought == "View the relevant lines"
    assert action == "str_replace_editor view /testbed/file.py --view_range 1 50"


def test_function_calling_parser_preserves_tuple_arguments_from_dict():
    parser = FunctionCallingParser()
    command = _str_replace_editor_command()
    model_response = {
        "message": "View the relevant lines",
        "tool_calls": [
            {
                "function": {
                    "name": "str_replace_editor",
                    "arguments": {"command": "view", "path": "/testbed/file.py", "view_range": (1, 50)},
                }
            }
        ],
    }

    _, action = parser(model_response, [command])

    assert action == "str_replace_editor view /testbed/file.py --view_range 1 50"


def test_function_calling_parser_still_quotes_string_arguments():
    parser = FunctionCallingParser()
    command = _str_replace_editor_command()
    model_response = {
        "message": "Replace text",
        "tool_calls": [
            {
                "function": {
                    "name": "str_replace_editor",
                    "arguments": {
                        "command": "str_replace",
                        "path": "/testbed/file.py",
                        "old_str": "hello world",
                    },
                }
            }
        ],
    }

    _, action = parser(model_response, [command])

    assert action == "str_replace_editor str_replace /testbed/file.py  --old_str 'hello world'"


def test_xml_function_calling_parser_preserves_array_arguments():
    parser = XMLFunctionCallingParser()
    command = _str_replace_editor_command()
    model_response = {
        "message": "\n".join(
            [
                "View the relevant lines",
                "<function=str_replace_editor>",
                "<parameter=command>view</parameter>",
                "<parameter=path>/testbed/file.py</parameter>",
                "<parameter=view_range>[1, 50]</parameter>",
                "</function>",
            ]
        )
    }

    thought, action = parser(model_response, [command])

    assert thought == "View the relevant lines"
    assert action == "str_replace_editor view /testbed/file.py --view_range 1 50"
