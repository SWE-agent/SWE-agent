import pytest

from sweagent.agent.history_processors import CacheControlHistoryProcessor


@pytest.mark.parametrize("last_type", ["text", "image_url"])
def test_cache_breakpoint_covers_entire_multimodal_message(last_type):
    last = (
        {"type": "text", "text": "closing text"}
        if last_type == "text"
        else {"type": "image_url", "image_url": {"url": "data:image/png;base64,aGVsbG8="}}
    )
    history = [
        {
            "role": "user",
            "message_type": "observation",
            "content": [{"type": "text", "text": "opening text", "cache_control": {"type": "ephemeral"}}, last],
        }
    ]
    result = CacheControlHistoryProcessor(last_n_messages=1)(history)
    blocks = result[0]["content"]
    assert "cache_control" not in blocks[0]
    assert blocks[-1]["cache_control"] == {"type": "ephemeral"}
    assert blocks[0]["text"] == "opening text"


def test_tool_cache_control_stays_on_message():
    history = [
        {
            "role": "tool",
            "message_type": "observation",
            "tool_call_ids": ["call"],
            "content": [{"type": "text", "text": "first"}, {"type": "text", "text": "last"}],
        }
    ]
    result = CacheControlHistoryProcessor()(history)
    assert result[0]["cache_control"] == {"type": "ephemeral"}
    assert all("cache_control" not in block for block in result[0]["content"])


@pytest.mark.parametrize("empty_content", [[], ""])
def test_empty_message_does_not_consume_cache_breakpoint(empty_content):
    history = [
        {"role": "user", "message_type": "observation", "content": "cache this"},
        {"role": "user", "message_type": "observation", "content": empty_content},
    ]
    result = CacheControlHistoryProcessor(last_n_messages=1)(history)
    assert result[0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert result[1]["content"] == empty_content
