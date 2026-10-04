from unittest.mock import patch

import pytest

from sweagent.agent.models import GenericAPIModelConfig, get_model
from sweagent.exceptions import ContextWindowExceededError
from sweagent.tools.parsing import FunctionCallingParser, Identity
from sweagent.tools.tools import ToolConfig
from sweagent.types import History


@pytest.mark.parametrize("function_calling", [True, False])
def test_input_budget_counts_only_transmitted_tool_schemas(function_calling):
    tools = ToolConfig(parse_function=FunctionCallingParser() if function_calling else Identity())
    model = get_model(GenericAPIModelConfig(name="gpt-4o", max_input_tokens=100), tools)
    history = History([{"role": "user", "content": "hello"}])

    def count_tokens(**kwargs):
        return 110 if kwargs.get("tools") else 10

    with (
        patch("litellm.utils.token_counter", side_effect=count_tokens) as counter,
        patch("litellm.completion", side_effect=RuntimeError("provider reached")) as completion,
    ):
        if function_calling:
            with pytest.raises(ContextWindowExceededError):
                model.query(history)
            completion.assert_not_called()
        else:
            with pytest.raises(RuntimeError, match="provider reached"):
                model.query(history)
            completion.assert_called_once()
    assert counter.call_args.kwargs.get("tools") == (tools.tools if function_calling else None)


def test_real_tool_schema_can_exceed_an_otherwise_valid_prompt_budget():
    from litellm.utils import token_counter

    history = History([{"role": "user", "content": "hello"}])
    message_tokens = token_counter(model="gpt-4o", messages=history)
    tools = ToolConfig(parse_function=FunctionCallingParser())
    assert token_counter(model="gpt-4o", messages=history, tools=tools.tools) > message_tokens
    model = get_model(GenericAPIModelConfig(name="gpt-4o", max_input_tokens=message_tokens), tools)
    with patch("litellm.completion") as completion:
        with pytest.raises(ContextWindowExceededError):
            model.query(history)
    completion.assert_not_called()
