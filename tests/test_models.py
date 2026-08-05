from __future__ import annotations

from unittest.mock import MagicMock, patch

import litellm
from pydantic import SecretStr

from sweagent import __version__
from sweagent.agent.models import GenericAPIModelConfig, get_model
from sweagent.tools.parsing import Identity
from sweagent.tools.tools import ToolConfig
from sweagent.types import History


def test_litellm_mock():
    model = get_model(
        GenericAPIModelConfig(
            name="gpt-4o",
            completion_kwargs={"mock_response": "Hello, world!"},
            api_key=SecretStr("dummy_key"),
            top_p=None,
        ),
        ToolConfig(
            parse_function=Identity(),
        ),
    )
    assert model.query(History([{"role": "user", "content": "Hello, world!"}])) == {"message": "Hello, world!"}  # type: ignore


def _make_mock_response(content: str = "mock", n_choices: int = 1) -> MagicMock:
    """Create a minimal mock response matching litellm's ModelResponse shape."""
    choices = []
    for _ in range(n_choices):
        choice = MagicMock()
        choice.message.content = content
        choice.message.tool_calls = None
        choices.append(choice)
    response = MagicMock()
    response.choices = choices
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 5
    return response


def _make_model():
    return get_model(
        GenericAPIModelConfig(
            name="gpt-4o",
            api_key=SecretStr("dummy_key"),
            top_p=None,
            per_instance_cost_limit=0,
            total_cost_limit=0,
        ),
        ToolConfig(parse_function=Identity()),
    )


def test_n_sampling_forwards_n_in_single_request():
    """n>1 sampling forwards n to the provider and sends a single request."""
    model = _make_model()
    mock_response = _make_mock_response(n_choices=3)
    with patch("litellm.completion", return_value=mock_response) as mock_completion:
        with patch("litellm.utils.token_counter", return_value=10):
            outputs = model._query([{"role": "user", "content": "test"}], n=3)
    mock_completion.assert_called_once()
    assert mock_completion.call_args.kwargs["n"] == 3
    assert len(outputs) == 3


def test_n_sampling_falls_back_when_provider_rejects_n():
    """Providers that reject n>1 fall back to one request per sample."""
    model = _make_model()
    responses = [
        litellm.exceptions.UnsupportedParamsError("provider does not support n"),
        _make_mock_response(),
        _make_mock_response(),
        _make_mock_response(),
    ]
    with patch("litellm.completion", side_effect=responses) as mock_completion:
        with patch("litellm.utils.token_counter", return_value=10):
            outputs = model._query([{"role": "user", "content": "test"}], n=3)
    assert len(outputs) == 3
    assert mock_completion.call_count == 4
    # Fallback requests are sent without n.
    assert all(call.kwargs["n"] is None for call in mock_completion.call_args_list[1:])


def test_n_sampling_tops_up_when_provider_returns_fewer_choices():
    """Providers that silently ignore n get the missing samples requested separately."""
    model = _make_model()
    responses = [
        _make_mock_response(n_choices=2),
        _make_mock_response(),
    ]
    with patch("litellm.completion", side_effect=responses) as mock_completion:
        with patch("litellm.utils.token_counter", return_value=10):
            outputs = model._query([{"role": "user", "content": "test"}], n=3)
    assert len(outputs) == 3
    assert mock_completion.call_count == 2
    assert mock_completion.call_args_list[0].kwargs["n"] == 3
    assert mock_completion.call_args_list[1].kwargs["n"] is None


def test_user_agent_header_default():
    """User-Agent header is added automatically when no extra_headers are set."""
    model = get_model(
        GenericAPIModelConfig(
            name="gpt-4o",
            api_key=SecretStr("dummy_key"),
            top_p=None,
            per_instance_cost_limit=0,
            total_cost_limit=0,
        ),
        ToolConfig(parse_function=Identity()),
    )
    mock_response = _make_mock_response()
    with patch("litellm.completion", return_value=mock_response) as mock_completion:
        model.query(History([{"role": "user", "content": "test"}]))
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args
        extra_headers = call_kwargs.kwargs.get("extra_headers", {})
        assert "User-Agent" in extra_headers
        assert extra_headers["User-Agent"] == f"swe-agent/{__version__}"


def test_user_agent_header_preserves_existing():
    """User-Agent header is not overridden when already provided by the user."""
    custom_ua = "my-custom-agent/1.0"
    model = get_model(
        GenericAPIModelConfig(
            name="gpt-4o",
            completion_kwargs={"extra_headers": {"User-Agent": custom_ua}},
            api_key=SecretStr("dummy_key"),
            top_p=None,
            per_instance_cost_limit=0,
            total_cost_limit=0,
        ),
        ToolConfig(parse_function=Identity()),
    )
    mock_response = _make_mock_response()
    with patch("litellm.completion", return_value=mock_response) as mock_completion:
        model.query(History([{"role": "user", "content": "test"}]))
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args
        extra_headers = call_kwargs.kwargs.get("extra_headers", {})
        assert extra_headers["User-Agent"] == custom_ua


def test_user_agent_header_with_other_extra_headers():
    """User-Agent header is added alongside other existing extra_headers."""
    model = get_model(
        GenericAPIModelConfig(
            name="gpt-4o",
            completion_kwargs={"extra_headers": {"X-Custom": "value"}},
            api_key=SecretStr("dummy_key"),
            top_p=None,
            per_instance_cost_limit=0,
            total_cost_limit=0,
        ),
        ToolConfig(parse_function=Identity()),
    )
    mock_response = _make_mock_response()
    with patch("litellm.completion", return_value=mock_response) as mock_completion:
        model.query(History([{"role": "user", "content": "test"}]))
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args
        extra_headers = call_kwargs.kwargs.get("extra_headers", {})
        assert extra_headers["User-Agent"] == f"swe-agent/{__version__}"
        assert extra_headers["X-Custom"] == "value"
