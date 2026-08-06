from unittest.mock import MagicMock

import pytest

from sweagent.agent.models import GenericAPIModelConfig, InstanceStats
from sweagent.agent.reviewer import Chooser, ChooserConfig, ReviewSubmission
from sweagent.exceptions import TotalCostLimitExceededError


def _make_chooser(model: MagicMock) -> Chooser:
    chooser = object.__new__(Chooser)
    chooser.config = ChooserConfig(
        model=GenericAPIModelConfig(name="test-model"),
        system_template="system",
        instance_template="problem: {{ problem_statement }}",
        submission_template="submission: {{ submission }}",
    )
    chooser.model = model
    chooser.logger = MagicMock()
    return chooser


def _make_submission() -> ReviewSubmission:
    return ReviewSubmission(
        trajectory=[],
        info={"submission": "solution", "exit_status": "submitted"},
        model_stats=InstanceStats(),
    )


def test_chooser_propagates_cost_limit_errors():
    model = MagicMock()
    model.query.side_effect = TotalCostLimitExceededError("budget exhausted")
    chooser = _make_chooser(model)

    with pytest.raises(TotalCostLimitExceededError):
        chooser.choose("problem", [_make_submission()])


def test_chooser_returns_empty_response_when_model_query_fails():
    model = MagicMock()
    model.query.side_effect = ValueError("invalid response")
    chooser = _make_chooser(model)

    output = chooser.choose("problem", [_make_submission()])

    assert output.chosen_idx == 0
    assert output.response == ""
