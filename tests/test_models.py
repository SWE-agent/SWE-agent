from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
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


def _make_mock_response(content: str = "mock") -> MagicMock:
    """Create a minimal mock response matching litellm's ModelResponse shape."""
    choice = MagicMock()
    choice.message.content = content
    choice.message.tool_calls = None
    response = MagicMock()
    response.choices = [choice]
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 5
    return response


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


@pytest.fixture
def litellm_model():
    return get_model(
        GenericAPIModelConfig(name="gpt-4o", api_key=SecretStr("dummy_key"), top_p=None),
        ToolConfig(parse_function=Identity()),
    )


def test_litellm_model_uses_native_n_when_supported(monkeypatch, litellm_model):
    calls = []

    def fake_single_query(messages, n=None, temperature=None):
        calls.append((n, temperature))
        return [{"message": str(index)} for index in range(n or 1)]

    monkeypatch.setattr(litellm_model, "_single_query", fake_single_query)
    monkeypatch.setattr("litellm.get_supported_openai_params", lambda **kwargs: ["n"])

    outputs = litellm_model._query([{"role": "user", "content": "test"}], n=3, temperature=0.4)

    assert calls == [(3, 0.4)]
    assert outputs == [{"message": "0"}, {"message": "1"}, {"message": "2"}]


def test_litellm_model_falls_back_when_native_n_is_unsupported(monkeypatch, litellm_model):
    calls = []

    def fake_single_query(messages, n=None, temperature=None):
        calls.append((n, temperature))
        return [{"message": "sample"}]

    monkeypatch.setattr(litellm_model, "_single_query", fake_single_query)
    monkeypatch.setattr("litellm.get_supported_openai_params", lambda **kwargs: None)

    outputs = litellm_model._query([{"role": "user", "content": "test"}], n=3, temperature=0.4)

    assert calls == [(None, 0.4), (None, 0.4), (None, 0.4)]
    assert outputs == [{"message": "sample"}] * 3


def test_litellm_model_falls_back_when_capabilities_cannot_be_resolved(monkeypatch, litellm_model):
    calls = []

    def fake_single_query(messages, n=None, temperature=None):
        calls.append((n, temperature))
        return [{"message": "sample"}]

    monkeypatch.setattr(litellm_model, "_single_query", fake_single_query)
    monkeypatch.setattr(
        "litellm.get_supported_openai_params", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("unknown model"))
    )

    outputs = litellm_model._query([{"role": "user", "content": "test"}], n=2, temperature=0.4)

    assert calls == [(None, 0.4), (None, 0.4)]
    assert outputs == [{"message": "sample"}] * 2
