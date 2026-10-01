import json
from pathlib import Path

import pytest

from sweagent.agent.history_processors import LastNObservations, TagToolCallObservations
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


@pytest.mark.parametrize("polling", [0, -1, -5])
def test_last_n_observations_rejects_nonpositive_polling(polling):
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="polling"):
        LastNObservations(n=3, polling=polling)


@pytest.mark.parametrize("polling", [1, 2, 3])
def test_last_n_observations_polling_keeps_recent_output(polling):
    history = [{"role": "user", "message_type": "observation", "content": f"output {i}"} for i in range(10)]
    result = LastNObservations(n=3, polling=polling)(history)
    assert result[0]["content"] == "output 0"
    assert [entry["content"] for entry in result[-3:]] == ["output 7", "output 8", "output 9"]
    assert count_elided_observations(result) == max(0, (10 // polling) * polling - 3 - 1)


def test_add_tag_to_edits(test_history: History):
    processor = TagToolCallObservations(tags={"test"}, function_names={"edit"})
    new_history = processor(test_history)
    for entry in new_history:
        if entry.get("action", "").startswith("edit "):  # type: ignore
            assert entry.get("tags") == ["test"], entry
