from __future__ import annotations

from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from sweagent.agent.action_sampler import BinaryTrajectoryComparison, BinaryTrajectoryComparisonConfig
from sweagent.agent.models import GenericAPIModelConfig, get_model
from sweagent.agent.problem_statement import EmptyProblemStatement
from sweagent.tools.parsing import Identity
from sweagent.tools.tools import ToolConfig, ToolHandler


def _make_mock_response(content: str) -> MagicMock:
    """Create a minimal mock response matching litellm's ModelResponse shape."""
    choice = MagicMock()
    choice.message.content = content
    choice.message.tool_calls = None
    response = MagicMock()
    response.choices = [choice]
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 5
    return response


def test_comparison_temperature_is_applied_to_comparison_query():
    """The pairwise comparison query must run at config.comparison_temperature."""
    model = get_model(
        GenericAPIModelConfig(
            name="gpt-4o",
            api_key=SecretStr("dummy_key"),
            temperature=0.0,
            top_p=None,
            per_instance_cost_limit=0,
            total_cost_limit=0,
        ),
        ToolConfig(parse_function=Identity()),
    )
    sampler = BinaryTrajectoryComparison(
        BinaryTrajectoryComparisonConfig(
            min_n_samples=2,
            max_n_samples=2,
            comparison_temperature=0.9,
        ),
        model,
        ToolHandler(ToolConfig(parse_function=Identity())),
    )
    responses = [
        _make_mock_response("action-a"),
        _make_mock_response("action-b"),
        _make_mock_response("the first one is better"),
    ]
    with patch("litellm.completion", side_effect=responses) as mock_completion:
        output = sampler.get_action(
            problem_statement=EmptyProblemStatement(),
            trajectory=[],
            history=[{"role": "user", "content": "solve it"}],
        )
    temperatures = [call.kwargs["temperature"] for call in mock_completion.call_args_list]
    assert len(temperatures) == 3  # two candidate samples + one comparison query
    assert temperatures[:2] == [0.0, 0.0]
    assert temperatures[2] == 0.9
    assert output.completion["message"] == "action-a"
