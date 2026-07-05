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


def _view_range_command() -> Command:
    return Command(
        name="view",
        docstring="View a file.",
        signature="view <path> <view_range>",
        arguments=[
            Argument(name="path", type="string", description="File path.", required=True),
            Argument(name="view_range", type="array", description="Line range.", required=True),
        ],
    )


def _xml_view_range_response(view_range: str) -> dict:
    return {
        "message": (
            "Let's view the file.\n"
            "<function=view>\n"
            "<parameter=path>/testbed/file.py</parameter>\n"
            f"<parameter=view_range>{view_range}</parameter>\n"
            "</function>"
        )
    }


def test_xml_function_calling_parser_view_range():
    parser = XMLFunctionCallingParser()
    command = _view_range_command()

    # A well-formed view_range parses into the command invocation.
    _, action = parser(_xml_view_range_response("[1, 20]"), [command])
    assert action == "view /testbed/file.py [1, 20]"

    # A value with trailing content after a valid [<int>, <int>] prefix must raise
    # FormatError (so the model is re-queried), not an uncaught JSONDecodeError.
    for malformed in ("[1,2]extra", "[1, 2] and more"):
        with pytest.raises(FormatError):
            parser(_xml_view_range_response(malformed), [command])
