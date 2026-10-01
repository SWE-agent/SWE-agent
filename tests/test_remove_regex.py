import copy

import pytest

from sweagent.agent.history_processors import RemoveRegex


@pytest.mark.parametrize("as_blocks", [False, True])
def test_default_diff_removal_preserves_intervening_output(as_blocks):
    text = "before<diff>first\npatch</diff>\nimportant test failure\n<diff>second patch</diff>after"
    content = [{"type": "text", "text": text}] if as_blocks else text
    history = [{"role": "user", "message_type": "observation", "content": content}]
    original = copy.deepcopy(history)
    result = RemoveRegex()(history)
    actual = result[0]["content"][0]["text"] if as_blocks else result[0]["content"]
    assert actual == "before\nimportant test failure\nafter"
    assert history == original


def test_diff_removal_preserves_last_message_and_custom_patterns():
    history = [
        {"role": "user", "message_type": "observation", "content": "<diff>old</diff>"},
        {"role": "user", "message_type": "observation", "content": "<diff>new</diff>"},
    ]
    result = RemoveRegex(keep_last=1)(history)
    assert result[0]["content"] == ""
    assert result[1]["content"] == "<diff>new</diff>"
    assert RemoveRegex(remove=["old"])(history)[0]["content"] == "<diff></diff>"
