import pytest

from sweagent.agent.history_processors import ClosedWindowHistoryProcessor


@pytest.mark.parametrize("content", ["1: first result\n2: second result\n", "Build failed\n42: error: missing name\n"])
def test_closed_window_preserves_numbered_output_without_file_header(content):
    history = [{"role": "user", "content": content, "message_type": "observation"}]
    assert ClosedWindowHistoryProcessor()(history) == history


def test_closed_window_only_elides_older_windows_for_the_same_file():
    def observation(content):
        return {"role": "user", "content": content, "message_type": "observation"}

    history = [
        observation("[File: example.py (2 lines total)]\n1: old\n2: text\n"),
        observation("1: unrelated command output\n"),
        observation("[File: example.py (2 lines total)]\n1: new\n2: text\n"),
    ]
    result = ClosedWindowHistoryProcessor()(history)
    assert len(result) == len(history)
    assert "Outdated window with 2 lines omitted" in result[0]["content"]
    assert result[1:] == history[1:]
    assert "1: old" in history[0]["content"]
