import json
from pathlib import Path

import pytest

from sweagent.agent.history_processors import CacheControlHistoryProcessor, LastNObservations, TagToolCallObservations
from sweagent.types import History


def get_history(traj_path: Path):
    return json.loads((traj_path).read_text())["history"]


def count_elided_observations(history: History):
    return len([entry for entry in history if "Old environment output" in entry["content"]])


@pytest.fixture
def test_history(test_trajectories_path: Path):
    return get_history(
        test_trajectories_path
        / "gpt4__swe-agent-test-repo__default_from_url__t-0.00__p-0.95__c-3.00__install-1/6e44b9__sweagenttestrepo-1c2844.traj"
    )


def test_last_n_observations(test_history: History):
    processor = LastNObservations(n=3)
    new_history = processor(test_history)
    total_observations = len([entry for entry in test_history if entry["message_type"] == "observation"])
    # extra -1 because instance template is kept
    expected_elided_observations = total_observations - 3 - 1
    assert count_elided_observations(new_history) == expected_elided_observations


def test_add_tag_to_edits(test_history: History):
    processor = TagToolCallObservations(tags={"test"}, function_names={"edit"})
    new_history = processor(test_history)
    for entry in new_history:
        if entry.get("action", "").startswith("edit "):  # type: ignore
            assert entry.get("tags") == ["test"], entry


@pytest.mark.parametrize(
    ("ttl", "expected_cache_control"),
    [
        ("5m", {"type": "ephemeral"}),
        ("1h", {"type": "ephemeral", "ttl": "1h"}),
    ],
)
def test_cache_control_ttl(ttl: str, expected_cache_control: dict[str, str]):
    history: History = [
        {"role": "user", "content": "Keep this prompt cached."},
        {"role": "tool", "content": [{"type": "text", "text": "Keep this tool output cached."}]},
    ]

    processed = CacheControlHistoryProcessor(last_n_messages=2, ttl=ttl)(history)  # type: ignore[arg-type]

    assert processed[0]["content"][0]["cache_control"] == expected_cache_control  # type: ignore[index]
    assert processed[1]["cache_control"] == expected_cache_control
