from __future__ import annotations

import numpy as np
import pytest

from sweagent.agent.models import InstanceStats
from sweagent.agent.reviewer import Reviewer, ReviewerConfig, ReviewSubmission, TrajFormatterConfig


class _Instance:
    def get_problem_statement(self) -> str:
        return "problem"

    def get_extra_fields(self) -> dict[str, str]:
        return {}


class _SequenceModel:
    def __init__(self, responses: list[object]):
        self._responses = iter(responses)

    def query(self, messages: list[dict[str, str]]) -> dict[str, str]:
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return {"message": response}  # type: ignore[dict-item]


def _reviewer(
    responses: list[object], *, reduce_by_std: float = 0.0, score_range: tuple[float, float] = (0, 10)
) -> Reviewer:
    config = ReviewerConfig(
        system_template="system",
        instance_template="{{ problem_statement }} {{ submission }}",
        traj_formatter=TrajFormatterConfig(),
        n_sample=5,
        reduce_by_std=reduce_by_std,
        score_range=score_range,
    )
    return Reviewer(config, _SequenceModel(responses))


def _submission() -> ReviewSubmission:
    return ReviewSubmission(
        trajectory=[],
        info={"exit_status": "submitted", "submission": "solution"},
        model_stats=InstanceStats(),
    )


@pytest.mark.parametrize(
    "failed_response",
    [RuntimeError("query failed"), "not a score", "Score: 42"],
    ids=["query exception", "unparsable reply", "out of range score"],
)
def test_failed_judge_samples_keep_the_configured_denominator(failed_response: object) -> None:
    reviewer = _reviewer([failed_response, "Score: 9", "Score: 9", "Score: 9", "Score: 9"])

    result = reviewer.review(_Instance(), _submission())

    # A failed sample has the existing all-failed fallback score (-100), rather
    # than disappearing from the n_sample-sized average.
    assert result.accept == pytest.approx((4 * 9 - 100) / 5)
    assert result.outputs == ["Score: 9"] * 4


def test_failed_judge_samples_preserve_reduce_by_std_penalty() -> None:
    reviewer = _reviewer(
        [
            RuntimeError("query failed"),
            RuntimeError("query failed"),
            RuntimeError("query failed"),
            RuntimeError("query failed"),
            "Score: 9",
        ],
        reduce_by_std=1.0,
    )

    result = reviewer.review(_Instance(), _submission())

    scores = [-100.0, -100.0, -100.0, -100.0, 9.0]
    assert result.accept == pytest.approx(sum(scores) / 5 - np.std(scores))
