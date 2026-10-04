from unittest.mock import patch

import pytest

from sweagent.agent.models import GenericAPIModelConfig, get_model
from sweagent.tools.parsing import Identity
from sweagent.tools.tools import ToolConfig
from sweagent.types import History


@pytest.mark.parametrize(
    ("limit", "kwargs", "expected"),
    [
        (128, {}, 128),
        (128, {"max_tokens": 512}, 128),
        (None, {"max_tokens": 512}, 512),
        (0, {"max_tokens": 512}, 512),
        (None, {}, None),
        (0, {}, None),
    ],
)
def test_output_limit_reaches_non_anthropic_provider(limit, kwargs, expected):
    model = get_model(
        GenericAPIModelConfig(
            name="gpt-4o", max_output_tokens=limit, completion_kwargs=kwargs, per_instance_cost_limit=0
        ),
        ToolConfig(parse_function=Identity()),
    )
    with patch("litellm.completion", side_effect=RuntimeError("stop before API call")) as completion:
        with pytest.raises(RuntimeError, match="stop before API call"):
            model.query(History([{"role": "user", "content": "hello"}]))
    assert completion.call_args.kwargs.get("max_tokens") == expected
    assert model.config.completion_kwargs == kwargs
