"""Our parsers parse output from the LM into thoughts and actions.

For example, our most basic parser is the `ThoughtActionParser`.
It expects the model response to be a discussion followed by a command wrapped in backticks like so:

```
Let's look at the files in the current directory.

Action:
 ```
ls -l
 ```
```

For models that support function calling, we instead recommend using the `FunctionCallingParser`.

To use a specific parser, set the `parse_function` key in your tool config to the `type` field of the parser.

```yaml
agent:
    tools:
        ...
        parse_function:
            type: "thought_action"
```

Or from the command line: `--agent.tools.parse_function.type=thought_action`.

!!! note "Describing available tools"
    If you do not use the `FunctionCallingParser`, you need to include documentation about the available tools
    in your system prompt. You can use the `{{command_docs}}` variable to include the automatically generated
    documentation or explicitly describe the available tools.
    Also see [#1130](https://github.com/SWE-agent/SWE-agent/issues/1130).
"""

import json
import re
import textwrap
from abc import ABC, abstractmethod
from shlex import quote
from textwrap import dedent
from typing import Any, Literal

from jinja2 import Template
from pydantic import BaseModel

from sweagent.exceptions import FormatError, FunctionCallingFormatError
from sweagent.tools.commands import Command
from sweagent.tools.utils import _should_quote


class AbstractParseFunction(ABC):
    """
    Abstract class for parsing functions.
    We use get to generate the right parser based on the name of the parser.
    """

    error_message: str

    @abstractmethod
    def __call__(self, model_response, commands: list[Command], strict=False) -> tuple[str, str]:
        raise NotImplementedError

    @property
    def format_error_template(self):
        return textwrap.dedent(self.error_message)


# DEFINE NEW PARSING FUNCTIONS BELOW THIS LINE


class ActionParser(AbstractParseFunction, BaseModel):
    """
    Expects the model response to be a single command.
    Example: "ls -l"
    """

    error_message: str = """\
    The command you provided was not recognized. Please specify one of the commands (+ any necessary arguments) from the following list in your response. Do not include any other text.

    COMMANDS:
    {command_docs}
    """

    type: Literal["action"] = "action"
    """Type for (de)serialization. Do not change."""

    def __call__(self, model_response: dict, commands: list[Command], strict=False):
        if model_response["message"].split():
            action = model_response["message"].strip().split()[0]
            if action in {command.name for command in commands}:
                return model_response["message"], model_response["message"]
        msg = "First word in model response is not a valid command."
        raise FormatError(msg)


class ActionOnlyParser(AbstractParseFunction, BaseModel):
    """Expects the model response to be a single command."""

    error_message: str = "No message found in model response."

    type: Literal["action_only"] = "action_only"
    """Type for (de)serialization. Do not change."""

    def __call__(self, model_response: dict, commands: list[Command], strict=False):
        return "", model_response["message"]


class ThoughtActionParser(AbstractParseFunction, BaseModel):
    """
    Expects the model response to be a discussion followed by a command wrapped in backticks.
    Example:
    Let's look at the files in the current directory.
    ```
    ls -l
    ```
    """

    error_message: str = dedent("""\
    Your output was not formatted correctly. You must always include one discussion and one command as part of your response. Make sure you do not have multiple discussion/command tags.
    Please make sure your output precisely matches the following format:
    DISCUSSION
    Discuss here with yourself about what your planning and what you're going to do in this step.

    ```
    command(s) that you're going to run
    ```
    """)

    type: Literal["thought_action"] = "thought_action"
    """Type for (de)serialization. Do not change."""

    def __call__(self, model_response: dict, commands: list[Command], strict=False):
        """
        Parses the action from the output of the API call.
        We assume that the action is the last code block in the model_response.
        We also assume that the action is not nested within another code block.
        This is problematic if the model_response includes many unnamed ``` blocks.
        For instance:
        ```
        This is a code block.
        ```
        ```
        This is another code block.
        ```

        In this case, only the second code block will be parsed as the action.
        """
        code_block_pat = re.compile(r"^```(\S*)\s*\n|^```\s*$", re.MULTILINE)
        stack = []
        last_valid_block = None
        for match in code_block_pat.finditer(model_response["message"]):
            if stack and not match.group(1):  # Closing of a code block
                start = stack.pop()
                # Check if it's not nested within another block
                if not stack:
                    last_valid_block = (start, match)
            elif match.group(1) is not None:  # Opening of a code block
                stack.append(match)
        if last_valid_block:
            start, end = last_valid_block
            thought = model_response["message"][: start.start()] + model_response["message"][end.end() :]
            return thought, model_response["message"][start.end() : end.start()]
        msg = "No action found in model response."
        raise FormatError(msg)


class XMLThoughtActionParser(AbstractParseFunction, BaseModel):
    """
    Expects the model response to be a discussion followed by a command wrapped in XML tags.
    Example:
    Let's look at the files in the current directory.
    <command>
    ls -l
    </command>
    """

    error_message: str = dedent("""\
    Your output was not formatted correctly. You must always include one discussion and one command as part of your response. Make sure you do not have multiple discussion/command tags.
    Please make sure your output precisely matches the following format:
    """)

    type: Literal["xml_thought_action"] = "xml_thought_action"
    """Type for (de)serialization. Do not change."""

    def __call__(self, model_response: dict, commands: list[Command], strict=False) -> tuple[str, str]:
        """
        Parses the action from the output of the API call.
        We assume that the action is the last code block in the model_response.
        We also assume that the action is not nested within another code block.
        This is problematic if the model_response includes many unnamed ``` blocks.
        For instance:
        <command>
        This is a code block.
        </command>
        <command>
        This is another code block.
        </command>

        In this case, only the second code block will be parsed as the action.
        """
        if "<command>" not in model_response["message"] or "</command>" not in model_response["message"]:
            msg = "No action found in model response."
            raise FormatError(msg)
        # `action` is everything between the last <command> and </command> tags
        start_action = model_response["message"].rfind("<command>") + len(
            "<command>"
        )  # start after the last <command> tag
        end_thought = model_response["message"].rfind("<command>")  # end before the last <command> tag
        end_action = model_response["message"].rfind("</command>")  # end before the last </command> tag
        restart_thought = model_response["message"].rfind("</command>") + len(
            "</command>"
        )  # start after the last </command> tag
        # `thought` is everything not in between <command> and </command> tags (includes after the last </command> tag)
        action = model_response["message"][start_action:end_action]
        thought = model_response["message"][:end_thought] + model_response["message"][restart_thought:]

        return thought.strip(), action.strip()


FN_REGEX_PATTERN = r"<function=([^>]+)>\n(.*?)</function>"
FN_PARAM_REGEX_PATTERN = r"<parameter=([^>]+)>(.*?)</parameter>"


class XMLFunctionCallingParser(AbstractParseFunction, BaseModel):
    """
    Expects the model response to be a tool calling format, where the command and parameters are specified
    in XML tags.
    Example:
    Let's look at the files in the current directory.
    <function=bash>
    <parameter=command>find /testbed -type f -name "_discovery.py"</parameter>
    </function>
    """

    error_message: str = dedent("""\
    {%- if error_code == "missing" -%}
    Your last output did not use any tool calls!
    Please make sure your output includes exactly _ONE_ function call!
    If you think you have already resolved the issue, please submit your changes by running the `submit` command.
    If you think you cannot solve the problem, please run `submit`.
    Else, please continue with a new tool call!
    {%- elif error_code == "multiple" -%}
    Your last output included multiple tool calls!
    Please make sure your output includes a thought and exactly _ONE_ function call.
    {%- elif error_code == "unexpected_arg" -%}
    Your action could not be parsed properly: {{exception_message}}.
    Make sure your function call doesn't include any extra arguments that are not in the allowed arguments, and only use the allowed commands.
    {%- else -%}
    Your action could not be parsed properly: {{exception_message}}.
    {% endif %}
    """)

    type: Literal["xml_function_calling"] = "xml_function_calling"

    def __call__(self, model_response: dict, commands: list[Command], strict=False) -> tuple[str, str]:
        fn_match = re.search(FN_REGEX_PATTERN, model_response["message"], re.DOTALL)
        if not fn_match:
            msg = "No function found in model response."
            raise FormatError(msg)
        fn_name = fn_match.group(1).strip()

        # Handle different names in SWE-agent vs. SWE-gym
        if fn_name == "execute_bash":
            fn_name = "bash"
        if fn_name == "finish":
            fn_name = "submit"

        fn_body = fn_match.group(2)
        thought = model_response["message"][: fn_match.start()] + model_response["message"][fn_match.end() :]
        thought = thought.strip()

        commands_dict = {c.name: c for c in commands}
        command = commands_dict.get(fn_name)
        if not command:
            msg = f"Command '{fn_name}' not found in list of available commands."
            raise FormatError(msg)

        params_dict = {
            param[0]: re.sub(r"^\n|\n$", "", param[1])
            for param in re.findall(FN_PARAM_REGEX_PATTERN, fn_body, re.DOTALL)
        }

        if "view_range" in params_dict:
            # Check that value is format as [x, y]
            v = params_dict["view_range"]
            if isinstance(v, str):
                if not re.match(r"\[\d+,\s*\d+\]", v):
                    msg = f"view_range must be in the format [<start>, <end>], got {v}."
                    raise FormatError(msg)
                params_dict["view_range"] = json.loads(v)

        # Check if all required arguments are there
        required_args = {arg.name for arg in command.arguments if arg.required}
        missing_args = required_args - params_dict.keys()
        if missing_args:
            msg = f"Required argument(s) missing: {', '.join(missing_args)}"
            raise FormatError(msg)

        # Check if all arguments are valid
        valid_args = {arg.name for arg in command.arguments}
        extra_args = set(params_dict.keys()) - valid_args
        if command.end_name:
            # sometimes the model will include the end_name in the arguments - just ignore it
            extra_args.discard(command.end_name)
        if extra_args:
            msg = f"Unexpected argument(s): {', '.join(extra_args)}"
            raise FormatError(msg)

        # Format arguments using their individual argument_format
        formatted_args = {
            arg.name: Template(arg.argument_format).render(
                value=quote(params_dict[arg.name])
                if _should_quote(params_dict[arg.name], command)
                else params_dict[arg.name]
            )
            if arg.name in params_dict
            else ""
            for arg in command.arguments
        }
        return thought, command.invoke_format.format(**formatted_args).strip()


class EditFormat(ThoughtActionParser, BaseModel):
    """
    Expects the model response to be a discussion followed by a command wrapped in backticks.
    Example:
    We'll replace the contents of the current window with the following:
    ```
    import os
    os.listdir()
    ```
    """

    error_message: str = dedent("""\
    Your output was not formatted correctly. You must wrap the replacement text in backticks (```).
    Please make sure your output precisely matches the following format:
    COMMENTS
    You can write comments here about what you're going to do if you want.

    ```
    New window contents.
    Make sure you copy the entire contents of the window here, with the required indentation.
    Make the changes to the window above directly in this window.
    Remember that all of the window's contents will be replaced with the contents of this window.
    Don't include line numbers in your response.
    ```
    """)

    type: Literal["edit_format"] = "edit_format"
    """Type for (de)serialization. Do not change."""


class Identity(AbstractParseFunction, BaseModel):
    """This parser does not do any parsing. It just returns the model response as both the thought and action."""

    error_message: str = """\
    It seems like something went wrong with your output. Please try again.
    """

    type: Literal["identity"] = "identity"
    """Type for (de)serialization. Do not change."""

    def __call__(self, model_response: dict, commands: list[Command], strict=False) -> tuple[str, str]:
        """
        This doesn't do any parsing. It just returns the model response as the thought and action.
        """
        return model_response["message"], model_response["message"]


class FunctionCallingParser(AbstractParseFunction, BaseModel):
    """Expects the model response to be a LiteLLM tool call."""

    error_message: str = dedent("""\
    {%- if error_code == "missing" -%}
    Your last output did not use any tool calls!
    Please make sure your output includes exactly _ONE_ function call!
    You must invoke the function directly using the function call format.
    You cannot invoke commands with ```, you have to use the function call format.
    If you think you have already resolved the issue, please submit your changes by running the `submit` command.
    If you think you cannot solve the problem, please run `exit_forfeit` (if available) or `submit`.
    Else, please continue with a new tool call!
    {%- elif error_code == "multiple" -%}
    Your last output included multiple tool calls!
    Please make sure your output includes a thought and exactly _ONE_ function call.
    {%- elif error_code == "unexpected_arg" -%}
    Your action could not be parsed properly: {{exception_message}}.
    Make sure your function call doesn't include any extra arguments that are not in the allowed arguments, and only use the allowed commands.
    {%- else -%}
    Your action could not be parsed properly: {{exception_message}}.
    {% endif %}
    """)

    type: Literal["function_calling"] = "function_calling"
    """Type for (de)serialization. Do not change."""

    def _parse_tool_call(self, tool_call: dict, commands: list[Command]):
        name = tool_call["function"]["name"]
        command = {c.name: c for c in commands}.get(name)
        if not command:
            msg = f"Command '{name}' not found in list of available commands."
            raise FunctionCallingFormatError(msg, "invalid_command")
        if not isinstance(tool_call["function"]["arguments"], dict):
            try:
                values = json.loads(tool_call["function"]["arguments"])
            except json.JSONDecodeError:
                msg = "Tool call arguments are not valid JSON."
                raise FunctionCallingFormatError(msg, "invalid_json")
        required_args = {arg.name for arg in command.arguments if arg.required}
        missing_args = required_args - values.keys()
        if missing_args:
            msg = f"Required argument(s) missing: {', '.join(missing_args)}"
            raise FunctionCallingFormatError(msg, "missing_arg")
        valid_args = {arg.name for arg in command.arguments}
        extra_args = set(values.keys()) - valid_args
        if command.end_name:
            # sometimes the model will include the end_name in the arguments - just ignore it
            extra_args.discard(command.end_name)
        if extra_args:
            msg = f"Unexpected argument(s): {', '.join(extra_args)}"
            raise FunctionCallingFormatError(msg, "unexpected_arg")

        def get_quoted_arg(value: Any) -> str:
            if isinstance(value, str):
                return quote(value) if _should_quote(value, command) else value
            # See https://github.com/SWE-agent/SWE-agent/issues/1159
            if value is None:
                return ""
            return str(value)

        formatted_args = {
            arg.name: Template(arg.argument_format).render(value=get_quoted_arg(values[arg.name]))
            if arg.name in values
            else ""
            for arg in command.arguments
        }
        return command.invoke_format.format(**formatted_args).strip()

    def __call__(self, model_response: dict, commands: list[Command], strict=False):
        message = model_response["message"]
        tool_calls = model_response.get("tool_calls", None)
        if tool_calls is None or len(tool_calls) != 1:
            num_tools = len(tool_calls) if tool_calls else 0
            msg = (
                f"Expected exactly one tool call in model response - received {num_tools} "
                f"tool calls with message: {message}"
            )
            error_code = "missing" if num_tools == 0 else "multiple"
            raise FunctionCallingFormatError(msg, error_code, num_tools=num_tools)
        tool_call = tool_calls[0]
        action = self._parse_tool_call(tool_call, commands)
        return message, action


class JsonParser(AbstractParseFunction, BaseModel):
    """Expects the model response to be a JSON object."""

    error_message: str = dedent("""\
    Your output could not be parsed as JSON. Please make sure your output 1) is valid JSON and
    2) Includes the "thought" and "command" fields.

    """)

    type: Literal["json"] = "json"
    """Type for (de)serialization. Do not change."""

    def __call__(self, model_response: dict, commands: list[Command], strict=False):
        """Parses the action from the output of the API call.
        We assume that model output is a JSON object with the following fields:
        {
            "thought": "discussion text here.",
            "command": {
                "arguments": {
                    "arg1": "value1",
                    "arg2": "value2",
                    ...
                },
                "name": "command_name"
            }
        }
        """
        try:
            data = json.loads(model_response["message"])
            if not isinstance(data, dict):
                msg = "Model output is not a JSON object."
                raise FormatError(msg)

            # Check if required keys are present
            required_keys = ["thought", "command"]
            for key in required_keys:
                if key not in data:
                    msg = f"Key '{key}' is missing from model output."
                    raise FormatError(msg)

            # Check structure of 'command' key
            data_command = data["command"]
            if not isinstance(data_command, dict):
                msg = "Value of 'command' key is not a JSON object."
                raise FormatError(msg)

            # Check if required keys are present in 'command' object
            command_keys = ["name"]
            for key in command_keys:
                if key not in data_command:
                    msg = f"Key '{key}' is missing from 'command' object."
                    raise FormatError(msg)

            thought = data["thought"]
            commands_dict = {c.name: c for c in commands}
            command = commands_dict.get(data_command["name"])

            # Handle command parsing based on strict mode
            if command is None:
                if strict:
                    msg = f"Command '{data_command['name']}' not found in list of available commands."
                    raise FormatError(msg)
                # In non-strict mode, just join command name with argument values
                return thought, " ".join([data_command["name"], *data_command.get("arguments", {}).values()])

            # Format arguments using their individual argument_format
            formatted_args = {}
            if command.arguments:
                for arg in command.arguments:
                    if arg.name in data_command.get("arguments", {}):
                        value = data_command["arguments"][arg.name]
                        if _should_quote(value, command):
                            value = quote(value)
                        formatted_args[arg.name] = Template(arg.argument_format).render(value=value)
                    elif strict and arg.required:
                        msg = f"Required argument '{arg.name}' missing for command '{command.name}'"
                        raise FormatError(msg)

            # Use the formatted arguments with invoke_format
            action = command.invoke_format.format(**formatted_args).strip()
            return thought, action
        except json.JSONDecodeError:
            msg = "Model output is not valid JSON."
            raise FormatError(msg)


ParseFunction = (
    ActionParser
    | ThoughtActionParser
    | ActionOnlyParser
    | XMLThoughtActionParser
    | XMLFunctionCallingParser
    | FunctionCallingParser
    | EditFormat
    | Identity
    | JsonParser
)
