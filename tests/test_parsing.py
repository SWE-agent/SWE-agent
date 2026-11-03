from __future__ import annotations

import pytest
from jinja2 import Template

from sweagent.exceptions import FormatError, FunctionCallingFormatError
from sweagent.tools.commands import Command
from sweagent.tools.parsing import (
    ActionParser,
    BashCodeBlockParser,
    EditFormat,
    FunctionCallingParser,
    Identity,
    JsonParser,
    SingleBashCodeBlockParser,
    ThoughtActionParser,
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


def test_bash_code_block_parser():
    parser = BashCodeBlockParser()
    msg = "Let's run some commands.\n```bash\necho 1\n```\nSome thoughts.\n```bash\necho 2\n```"
    thought, action = parser({"message": msg}, [])
    assert action == "echo 1\necho 2"
    assert "<extracted_code_block>" in thought

    with pytest.raises(FormatError, match="No bash code blocks were detected"):
        parser({"message": "No bash blocks here"}, [])


def test_single_bash_code_block_parser():
    parser = SingleBashCodeBlockParser()
    msg = "THOUGHT: inspect files\n```bash\nls -la\n```"
    thought, action = parser({"message": msg}, [])
    assert action == "ls -la"
    assert "<extracted_code_block>" in thought

    with pytest.raises(FormatError, match="No bash code blocks were detected"):
        parser({"message": "No bash blocks here"}, [])

    multiple = "```bash\ncmd1\n```\n```bash\ncmd2\n```"
    with pytest.raises(FormatError, match="multiple bash code blocks"):
        parser({"message": multiple}, [])


@pytest.mark.parametrize("parser_cls", [BashCodeBlockParser, SingleBashCodeBlockParser])
def test_bash_code_block_parser_crlf_and_trailing_whitespace(parser_cls):
    parser = parser_cls()
    msg = "THOUGHT: run command\r\n```bash   \r\necho hello\r\n```"
    thought, action = parser({"message": msg}, [])
    assert action == "echo hello"
    assert "<extracted_code_block>" in thought


@pytest.mark.parametrize(
    ("parser_cls", "error_match"),
    [
        (BashCodeBlockParser, r"code block\(s\) in your response are empty"),
        (SingleBashCodeBlockParser, r"code block in your response is empty"),
    ],
)
def test_bash_code_block_parser_empty_raises_format_error(parser_cls, error_match):
    parser = parser_cls()
    empty_msg = "THOUGHT: nothing\n```bash\n   \n```"
    with pytest.raises(FormatError, match=error_match):
        parser({"message": empty_msg}, [])
