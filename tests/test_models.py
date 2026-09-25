from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from sweagent import __version__
from sweagent.agent.models import GenericAPIModelConfig, ReplayModel, ReplayModelConfig, get_model
from sweagent.tools.parsing import FunctionCallingParser, Identity
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


def _make_replay_model(replay_file, parse_function=Identity()) -> ReplayModel:
    return ReplayModel(
        ReplayModelConfig(replay_path=replay_file),
        ToolConfig(parse_function=parse_function),
    )


def _write_replay_file(path, *instances: list) -> None:
    """Write a replay file with one `{instance_id: [actions]}` object per line,
    the format written by `run-replay`'s `_create_actions_file`."""
    path.write_text("\n".join(json.dumps({f"instance-{i + 1}": actions}) for i, actions in enumerate(instances)))


def test_replay_model_advances_after_dict_submit_action(tmp_path):
    """Replaying the submit action of an instance written as a dict (the format
    written by `run-replay`) must advance to the next instance's actions."""
    replay_file = tmp_path / "replay.json"
    _write_replay_file(
        replay_file,
        [
            {"message": "Let's start.\n```\necho step-one-1\n```"},
            {"message": "Done, submitting.\n```\nsubmit\n```"},
        ],
        [{"message": "```\necho step-two-1\n```"}],
    )
    model = _make_replay_model(replay_file)
    history = History([])
    assert model.query(history) == {"message": "Let's start.\n```\necho step-one-1\n```"}
    assert model.query(history) == {"message": "Done, submitting.\n```\nsubmit\n```"}
    # The submit action ended instance 1, so the next query replays instance 2
    assert model.query(history) == {"message": "```\necho step-two-1\n```"}


def test_replay_model_advances_after_function_calling_submit_action(tmp_path):
    """Replaying a submit tool call must advance to the next instance's actions."""
    replay_file = tmp_path / "replay.json"
    submit_call = {
        "type": "function",
        "id": "call_submit",
        "function": {"name": "submit", "arguments": "{}"},
    }
    _write_replay_file(
        replay_file,
        [
            {
                "message": "Editing the file.",
                "tool_calls": [
                    {"type": "function", "id": "call_1", "function": {"name": "str_replace_editor", "arguments": "{}"}}
                ],
            },
            {"message": "Calling `submit` to submit.", "tool_calls": [submit_call]},
        ],
        [{"message": "```\necho step-two-1\n```"}],
    )
    model = _make_replay_model(replay_file, parse_function=FunctionCallingParser())
    history = History([])
    assert model.query(history)["tool_calls"][0]["function"]["name"] == "str_replace_editor"
    assert model.query(history)["tool_calls"] == [submit_call]
    # The submit action ended instance 1, so the next query replays instance 2
    assert model.query(history) == {"message": "```\necho step-two-1\n```"}


def test_replay_model_advances_after_string_submit_action(tmp_path):
    """Legacy replay files store plain string actions with `submit` as the last one."""
    replay_file = tmp_path / "replay.json"
    _write_replay_file(replay_file, ["echo one", "submit"], ["echo two"])
    model = _make_replay_model(replay_file)
    history = History([])
    assert model.query(history) == {"message": "echo one"}
    assert model.query(history) == {"message": "submit"}
    # The submit action ended instance 1, so the next query replays instance 2
    assert model.query(history) == {"message": "echo two"}


def test_replay_model_advances_after_auto_submission(tmp_path):
    """If a replayed trajectory ends without a submit action, the auto-generated
    submission should advance to the next instance's actions instead of
    auto-submitting over and over."""
    replay_file = tmp_path / "replay.json"
    _write_replay_file(
        replay_file,
        [{"message": "```\necho step-one-1\n```"}],
        [{"message": "```\necho step-two-1\n```"}],
    )
    model = _make_replay_model(replay_file)
    history = History([])
    assert model.query(history) == {"message": "```\necho step-one-1\n```"}
    # Instance 1 ran out of actions without submitting, so the model submits now
    assert model.query(history) == {"message": "```\nsubmit\n```"}
    # The next query replays instance 2 instead of auto-submitting again
    assert model.query(history) == {"message": "```\necho step-two-1\n```"}


def test_replay_model_auto_submits_when_file_exhausted(tmp_path):
    """Queries after the last instance's submit action auto-submit instead of crashing."""
    replay_file = tmp_path / "replay.json"
    _write_replay_file(
        replay_file,
        [
            {"message": "```\necho step-one-1\n```"},
            {"message": "```\nsubmit\n```"},
        ],
        [
            {"message": "```\necho step-two-1\n```"},
            {"message": "```\nsubmit\n```"},
        ],
    )
    model = _make_replay_model(replay_file)
    history = History([])
    assert model.query(history) == {"message": "```\necho step-one-1\n```"}
    assert model.query(history) == {"message": "```\nsubmit\n```"}
    assert model.query(history) == {"message": "```\necho step-two-1\n```"}
    assert model.query(history) == {"message": "```\nsubmit\n```"}
    # Both instances are done: any further query submits instead of crashing
    assert model.query(history) == {"message": "```\nsubmit\n```"}
