from __future__ import annotations

from unittest.mock import patch

import litellm
import pytest

from sweagent.agent.models import GenericAPIModelConfig, LiteLLMModel, RetryConfig
from sweagent.tools.parsing import ActionParser
from sweagent.tools.tools import ToolConfig


def _fake_response():
    message = type(
        "M",
        (),
        {"content": "action: no_action", "tool_calls": None, "thinking_blocks": None},
    )()
    choice = type("C", (), {"message": message, "finish_reason": "stop"})()
    usage = type("U", (), {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110})()
    return type("R", (), {"choices": [choice], "usage": usage, "model": "gpt-4o"})()


@pytest.fixture
def model():
    model = LiteLLMModel(
        GenericAPIModelConfig(
            name="gpt-4o",
            api_key="dummy",
            retry=RetryConfig(retries=2, min_wait=0.01, max_wait=0.02),
            per_instance_cost_limit=0,
            total_cost_limit=0,
        ),
        ToolConfig(parse_function=ActionParser()),
    )
    model._history_to_messages = lambda history: [{"role": "user", "content": "test"}]
    return model


def test_failed_sample_does_not_rebill_earlier_samples(model):
    """A retryable failure on sample 2 must not re-issue sample 1."""
    calls = []

    def fake_completion(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            msg = "rate limited"
            raise litellm.exceptions.RateLimitError(message=msg, llm_provider="openai", model="gpt-4o")
        return _fake_response()

    with patch("litellm.completion", side_effect=fake_completion):
        outputs = model.query(None, n=2)

    assert len(outputs) == 2
    # 3 real calls: sample 1, sample 2 (rate limited), sample 2 again.  Sample 1
    # is not re-issued, so it is billed exactly once.
    assert len(calls) == 3
    assert model.stats.api_calls == 2


def test_explicit_temperature_reaches_the_provider(model):
    """`temperature=` overrides are documented (comparison_temperature) - honour them."""
    calls = []

    def fake_completion(*args, **kwargs):
        calls.append(kwargs)
        return _fake_response()

    with patch("litellm.completion", side_effect=fake_completion):
        model.query(None, temperature=0.75)
        model.query(None, n=2, temperature=0.25)

    assert [call["temperature"] for call in calls] == [0.75, 0.25, 0.25]
