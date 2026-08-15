from __future__ import annotations

import pytest

from sweagent.agent.models import GenericAPIModelConfig, InstanceStats
from sweagent.agent.problem_statement import TextProblemStatement
from sweagent.agent.reviewer import (
    ChooserConfig,
    ChooserRetryLoopConfig,
    PreselectorConfig,
    ReviewSubmission,
)


def _model_config() -> GenericAPIModelConfig:
    return GenericAPIModelConfig(name="test-model", api_key="dummy")


def _loop_config(*, with_preselector: bool = False) -> ChooserRetryLoopConfig:
    return ChooserRetryLoopConfig(
        chooser=ChooserConfig(
            model=_model_config(),
            system_template="pick",
            instance_template="{{problem_statement}}",
            submission_template="{{submission}}",
            preselector=PreselectorConfig(
                model=_model_config(),
                system_template="preselect",
                instance_template="{{problem_statement}}",
                submission_template="{{submission}}",
            )
            if with_preselector
            else None,
        ),
        max_attempts=10,
        min_budget_for_new_attempt=1.0,
        cost_limit=6.0,
    )


def _submission(cost: float) -> ReviewSubmission:
    return ReviewSubmission(
        trajectory=[],
        info={"submission": "pass", "exit_status": "submitted"},
        model_stats=InstanceStats(instance_cost=cost, api_calls=1),
    )


def test_chooser_cost_is_reported():
    loop = _loop_config().get_retry_loop(TextProblemStatement(text="fix the bug"))
    loop.on_submit(_submission(2.0))
    loop.on_submit(_submission(3.0))

    # Stand in for a chooser query that has already happened.
    loop._chooser.model.stats = InstanceStats(instance_cost=6.75, api_calls=1)

    assert loop.review_model_stats.instance_cost == pytest.approx(6.75)
    assert loop._total_stats.instance_cost == pytest.approx(11.75)


def test_preselector_cost_is_reported():
    loop = _loop_config(with_preselector=True).get_retry_loop(TextProblemStatement(text="fix the bug"))
    loop.on_submit(_submission(1.0))

    chooser = loop._chooser
    chooser.model.stats = InstanceStats(instance_cost=2.0, api_calls=1)
    # `choose()` builds the preselector lazily; once built its spend must count.
    chooser._preselector = chooser.config.preselector and _PreselectorStub(0.5)

    assert loop.review_model_stats.instance_cost == pytest.approx(2.5)
    assert loop._total_stats.instance_cost == pytest.approx(3.5)


def test_retry_budget_is_driven_by_attempt_cost():
    """`cost_limit` is documented as excluding the choosing step.

    The chooser has not run while `retry()` is being asked, so reporting its
    spend through `_total_stats` leaves the budget decisions untouched.
    """
    loop = _loop_config().get_retry_loop(TextProblemStatement(text="fix the bug"))
    loop.on_submit(_submission(2.0))
    assert loop.retry() is True

    loop.on_submit(_submission(3.5))  # $5.5 of $6 spent, under the $1 floor
    assert loop.retry() is False


class _PreselectorStub:
    """Minimal stand-in exposing the one attribute `Chooser.stats` reads."""

    def __init__(self, cost: float):
        self.model = type("M", (), {"stats": InstanceStats(instance_cost=cost, api_calls=1)})()
