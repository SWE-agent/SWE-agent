from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from sweagent.agent.models import (
    GenericAPIModelConfig,
    InstanceStats,
    LiteLLMModel,
    extract_cache_usage,
)
from sweagent.tools.parsing import ActionParser
from sweagent.tools.tools import ToolConfig


def _anthropic_usage(read: int, write: int):
    return SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=10,
        total_tokens=110,
        cache_read_input_tokens=read,
        cache_creation_input_tokens=write,
    )


def _openai_usage(cached: int):
    return SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=10,
        total_tokens=110,
        prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
    )


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        (_anthropic_usage(1200, 800), (1200, 800)),
        (_anthropic_usage(0, 0), (0, 0)),
        (_openai_usage(1536), (1536, 0)),
        (_openai_usage(0), (0, 0)),
        (SimpleNamespace(prompt_tokens=10, completion_tokens=1), (0, 0)),
        (None, (0, 0)),
    ],
)
def test_extract_cache_usage(usage, expected):
    assert extract_cache_usage(SimpleNamespace(usage=usage)) == expected


def test_extract_cache_usage_without_usage_attribute():
    assert extract_cache_usage(object()) == (0, 0)


def test_cache_tokens_reach_the_stats():
    model = LiteLLMModel(
        GenericAPIModelConfig(name="gpt-4o", api_key="dummy", per_instance_cost_limit=0, total_cost_limit=0),
        ToolConfig(parse_function=ActionParser()),
    )
    model._history_to_messages = lambda history: [{"role": "user", "content": "test"}]

    message = SimpleNamespace(content="action: no_action", tool_calls=None, thinking_blocks=None)
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason="stop")],
        usage=_anthropic_usage(1200, 800),
        model="gpt-4o",
    )

    with patch("litellm.completion", return_value=response):
        model.query(None)
        model.query(None)

    assert model.stats.cache_read_tokens == 2400
    assert model.stats.cache_write_tokens == 1600


def test_cache_tokens_add_across_instance_stats():
    total = InstanceStats(cache_read_tokens=10, cache_write_tokens=3) + InstanceStats(
        cache_read_tokens=5, cache_write_tokens=1
    )
    assert (total.cache_read_tokens, total.cache_write_tokens) == (15, 4)


def test_old_trajectories_still_parse():
    """The new fields default to 0, so stats written before this change still load."""
    stats = InstanceStats.model_validate({"instance_cost": 1.0, "tokens_sent": 5, "tokens_received": 2, "api_calls": 1})
    assert (stats.cache_read_tokens, stats.cache_write_tokens) == (0, 0)
