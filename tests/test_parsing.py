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
    XMLThoughtActionParser,
    _coerce_array_argument,
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


def _view_range_command() -> Command:
    """A str_replace_editor-like command with an array-typed ``view_range`` arg."""
    return Command(
        name="str_replace_editor",
        docstring="",
        signature="str_replace_editor <command> <path> [<view_range>]",
        arguments=[
            Argument(name="command", type="string", description="", required=True),
            Argument(name="path", type="string", description="", required=True),
            Argument(
                name="view_range",
                type="array",
                items={"type": "integer"},
                description="",
                required=False,
                argument_format="--view_range {{value|join(' ')}}",
            ),
        ],
    )


def test_coerce_array_argument():
    array_arg = Argument(name="view_range", type="array", description="", required=False)
    string_arg = Argument(name="path", type="string", description="", required=False)
    # JSON-string-encoded array is parsed back into a list
    assert _coerce_array_argument("[1, 50]", array_arg) == [1, 50]
    # Actual lists pass through untouched
    assert _coerce_array_argument([1, 50], array_arg) == [1, 50]
    # Non-array-typed args are never coerced
    assert _coerce_array_argument("[1, 50]", string_arg) == "[1, 50]"
    # Unparseable / non-list values are returned unchanged
    assert _coerce_array_argument("not json", array_arg) == "not json"
    assert _coerce_array_argument("5", array_arg) == "5"


def test_function_calling_parser_array_argument_as_string():
    """Regression test for #1182: an array argument returned as a JSON string
    must not be rendered character-by-character (e.g. ``[ 1 ,   5 0 ]``)."""
    parser = FunctionCallingParser()
    command = _view_range_command()

    # The model returns view_range as a proper JSON array.
    as_list = {
        "message": "look",
        "tool_calls": [
            {
                "function": {
                    "name": "str_replace_editor",
                    "arguments": '{"command": "view", "path": "/testbed/x.py", "view_range": [1, 50]}',
                }
            }
        ],
    }
    _, action = parser(as_list, [command])
    assert action == "str_replace_editor view /testbed/x.py --view_range 1 50"

    # The model returns view_range as a JSON-encoded *string* (the #1182 case).
    as_string = {
        "message": "look",
        "tool_calls": [
            {
                "function": {
                    "name": "str_replace_editor",
                    "arguments": '{"command": "view", "path": "/testbed/x.py", "view_range": "[1, 50]"}',
                }
            }
        ],
    }
    _, action = parser(as_string, [command])
    assert action == "str_replace_editor view /testbed/x.py --view_range 1 50"
