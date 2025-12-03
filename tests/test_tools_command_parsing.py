import pytest

from sweagent.tools.commands import Argument, Command


def test_command_parsing_formats():
    """Test various signature formats and default parsing."""
    # Default format (no signature)
    command = Command(
        name="test_cmd",
        docstring="A test command",
        arguments=[
            Argument(name="arg1", type="string", description="First argument", required=True),
            Argument(name="arg2", type="integer", description="Second argument", required=False),
        ],
    )
    assert command.invoke_format == "test_cmd {arg1} {arg2} "

    # Angle brackets
    command = Command(
        name="goto",
        signature="goto <line_number>",
        docstring="moves the window to show line_number",
        arguments=[Argument(name="line_number", type="integer", description="line number", required=True)],
    )
    assert command.invoke_format == "goto {line_number}"

    # Optional brackets (stripped in invoke_format)
    command = Command(
        name="open",
        signature='open "<path>" [<line_number>]',
        docstring="opens file at path",
        arguments=[
            Argument(name="path", type="string", description="file path", required=True),
            Argument(name="line_number", type="integer", description="line number", required=False),
        ],
    )
    assert command.invoke_format == 'open "{path}" {line_number}'

    # Flag-style arguments
    command = Command(
        name="grep",
        signature="grep --pattern <pattern> --file <file>",
        docstring="search for pattern in file",
        arguments=[
            Argument(name="pattern", type="string", description="search pattern", required=True),
            Argument(name="file", type="string", description="file to search", required=True),
        ],
    )
    assert command.invoke_format == "grep --pattern {pattern} --file {file}"

    # No arguments
    command = Command(name="scroll_up", signature="scroll_up", docstring="scrolls up", arguments=[])
    assert command.invoke_format == "scroll_up"


def test_argument_validation():
    """Test argument validation rules."""
    # Required arguments must come before optional ones
    with pytest.raises(ValueError, match="Required argument.*cannot come after optional arguments"):
        Command(
            name="bad_order",
            docstring="bad argument order",
            arguments=[
                Argument(name="optional", type="string", description="optional", required=False),
                Argument(name="required", type="string", description="required", required=True),
            ],
        )

    # Duplicate argument names
    with pytest.raises(ValueError, match="Duplicate argument names"):
        Command(
            name="duplicate",
            docstring="duplicate args",
            arguments=[
                Argument(name="arg1", type="string", description="first", required=True),
                Argument(name="arg1", type="string", description="duplicate", required=True),
            ],
        )


def test_argument_name_patterns():
    """Test valid and invalid argument name patterns."""
    # Valid names including single characters
    valid_names = ["a", "x", "n", "simple", "with_underscore", "with-dash", "with123numbers", "_starts_with_underscore"]

    for name in valid_names:
        command = Command(
            name="test",
            docstring="test",
            arguments=[Argument(name=name, type="string", description="test", required=True)],
        )
        assert command.arguments[0].name == name

    # Invalid names
    invalid_names = ["123starts_with_number", ""]

    for name in invalid_names:
        with pytest.raises(ValueError, match="Invalid argument name"):
            Command(
                name="test",
                docstring="test",
                arguments=[Argument(name=name, type="string", description="test", required=True)],
            )


def test_signature_argument_consistency():
    """Test that signatures and arguments must be consistent."""
    # Missing argument in signature
    with pytest.raises(ValueError, match="Missing argument.*in signature"):
        Command(
            name="missing_arg",
            signature="missing_arg <existing_arg>",
            docstring="missing argument in signature",
            arguments=[
                Argument(name="existing_arg", type="string", description="exists", required=True),
                Argument(name="missing_arg", type="string", description="not in signature", required=True),
            ],
        )

    # Extra argument in signature
    with pytest.raises(ValueError, match="Argument names.*do not match"):
        Command(
            name="extra_arg",
            signature="extra_arg <arg1> <extra>",
            docstring="extra argument in signature",
            arguments=[Argument(name="arg1", type="string", description="exists", required=True)],
        )


def test_function_calling_tool_generation():
    """Test OpenAI function calling tool generation."""
    command = Command(
        name="test_function",
        docstring="A test function for OpenAI",
        arguments=[
            Argument(name="required_arg", type="string", description="Required string argument", required=True),
            Argument(
                name="enum_arg", type="string", description="Enum argument", required=True, enum=["option1", "option2"]
            ),
            Argument(name="optional_arg", type="integer", description="Optional integer argument", required=False),
        ],
    )

    tool = command.get_function_calling_tool()

    assert tool["type"] == "function"
    assert tool["function"]["name"] == "test_function"
    assert tool["function"]["description"] == "A test function for OpenAI"

    properties = tool["function"]["parameters"]["properties"]
    assert properties["required_arg"]["type"] == "string"
    assert properties["optional_arg"]["type"] == "integer"
    assert properties["enum_arg"]["enum"] == ["option1", "option2"]

    required = tool["function"]["parameters"]["required"]
    assert "required_arg" in required
    assert "enum_arg" in required
    assert "optional_arg" not in required


def test_multiline_command():
    """Test multi-line commands with end markers."""
    command = Command(
        name="edit",
        signature="edit <filename>",
        docstring="Edit a file with multi-line content",
        end_name="EOF",
        arguments=[Argument(name="filename", type="string", description="file to edit", required=True)],
    )

    assert command.invoke_format == "edit {filename}"
    assert command.end_name == "EOF"


def test_custom_argument_format():
    """Test custom argument formatting."""
    command = Command(
        name="custom_format",
        docstring="Test custom argument formatting",
        arguments=[
            Argument(
                name="arg1",
                type="string",
                description="Custom formatted argument",
                required=True,
                argument_format="--{value}",
            )
        ],
    )

    assert command.arguments[0].argument_format == "--{value}"
    assert command.invoke_format == "custom_format {arg1} "
