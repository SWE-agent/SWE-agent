from types import SimpleNamespace

from sweagent.agent.models import InstanceStats
from sweagent.agent.reviewer import (
    ReviewSubmission,
    ReviewerResult,
    ScoreRetryLoop,
)


def test_score_retry_loop_prefers_zero_api_calls_for_tied_scores():
    loop = object.__new__(ScoreRetryLoop)
    loop.logger = SimpleNamespace(
        debug=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
    )

    loop._reviews = [
        ReviewerResult(
            accept=0.9,
            outputs=[],
            messages=[],
        ),
        ReviewerResult(
            accept=0.9,
            outputs=[],
            messages=[],
        ),
    ]
    loop._submissions = [
        ReviewSubmission(
            trajectory=[],
            info={},
            model_stats=InstanceStats(api_calls=0),
        ),
        ReviewSubmission(
            trajectory=[],
            info={},
            model_stats=InstanceStats(api_calls=5),
        ),
    ]

    assert loop.get_best() == 0
