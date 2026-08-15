from __future__ import annotations

import pytest

from sweagent.agent.history_processors import CacheControlHistoryProcessor


def _history() -> list[dict]:
    return [
        {"role": "system", "content": "system", "message_type": "system_prompt", "agent": "main"},
        {"role": "user", "content": "first", "message_type": "observation", "agent": "main"},
        {"role": "assistant", "content": "thought", "message_type": "action", "agent": "main"},
        {"role": "user", "content": "second", "message_type": "observation", "agent": "main"},
    ]


def _cache_controls(history: list[dict]) -> list[dict]:
    marks = []
    for entry in history:
        if isinstance(entry.get("content"), list):
            marks += [item["cache_control"] for item in entry["content"] if "cache_control" in item]
        if "cache_control" in entry:
            marks.append(entry["cache_control"])
    return marks


def test_default_sends_no_ttl():
    """Unchanged behaviour: no `ttl` key, so the provider default applies."""
    processed = CacheControlHistoryProcessor()(_history())  # type: ignore[arg-type]
    marks = _cache_controls(processed)
    assert marks
    assert all(mark == {"type": "ephemeral"} for mark in marks)


@pytest.mark.parametrize("ttl", ["1h", "5m"])
def test_ttl_is_forwarded(ttl):
    processed = CacheControlHistoryProcessor(ttl=ttl)(_history())  # type: ignore[arg-type]
    marks = _cache_controls(processed)
    assert marks
    assert all(mark == {"type": "ephemeral", "ttl": ttl} for mark in marks)


def test_marks_are_not_shared_between_entries():
    """Each breakpoint gets its own dict, so mutating one cannot alter another."""
    processed = CacheControlHistoryProcessor(last_n_messages=2, ttl="1h")(_history())  # type: ignore[arg-type]
    marks = _cache_controls(processed)
    assert len(marks) >= 2
    marks[0]["ttl"] = "mutated"
    assert marks[1]["ttl"] == "1h"


def test_tool_entries_carry_the_ttl():
    history = [{"role": "tool", "content": "output", "message_type": "observation", "agent": "main"}]
    processed = CacheControlHistoryProcessor(ttl="1h")(history)  # type: ignore[arg-type]
    assert processed[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert all("cache_control" not in item for item in processed[0]["content"])
