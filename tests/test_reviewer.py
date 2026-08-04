from unittest.mock import MagicMock, patch

from sweagent.agent.models import GenericAPIModelConfig, InstanceStats
from sweagent.agent.problem_statement import TextProblemStatement
from sweagent.agent.reviewer import (
    ChooserConfig,
    ChooserRetryLoopConfig,
    PreselectorConfig,
    ReviewSubmission,
)


def _model(stats: InstanceStats, response: str = "0") -> MagicMock:
    model = MagicMock()
    model.stats = stats
    model.query.return_value = {"message": response}
    return model


def _chooser_config(*, preselector: bool = False) -> ChooserRetryLoopConfig:
    model = GenericAPIModelConfig(name="test-model")
    preselector_config = None
    if preselector:
        preselector_config = PreselectorConfig(
            model=model,
            system_template="preselect",
            instance_template="{{ problem_statement }}",
            submission_template="{{ submission }}",
        )
    return ChooserRetryLoopConfig(
        chooser=ChooserConfig(
            model=model,
            system_template="choose",
            instance_template="{{ problem_statement }}",
            submission_template="{{ submission }}",
            preselector=preselector_config,
        ),
        max_attempts=10,
        cost_limit=6.0,
    )


def _submission(cost: float) -> ReviewSubmission:
    return ReviewSubmission(
        trajectory=[],
        info={"submission": "patch", "exit_status": "submitted"},
        model_stats=InstanceStats(instance_cost=cost, api_calls=1),
    )


def test_chooser_cost_is_reported_without_counting_toward_attempt_budget() -> None:
    chooser_model = _model(InstanceStats(instance_cost=6.75, api_calls=1))
    with patch("sweagent.agent.reviewer.get_model", return_value=chooser_model):
        loop = _chooser_config().get_retry_loop(TextProblemStatement(text="fix the bug"))

    loop.on_submit(_submission(5.0))

    assert loop.review_model_stats == InstanceStats(instance_cost=6.75, api_calls=1)
    assert loop._total_stats == InstanceStats(instance_cost=11.75, api_calls=2)
    assert loop.retry()


def test_preselector_cost_is_included_when_preselection_runs() -> None:
    chooser_model = _model(InstanceStats(instance_cost=2.0, api_calls=1))
    preselector_model = _model(InstanceStats(instance_cost=1.5, api_calls=1), response="0 1")
    with patch("sweagent.agent.reviewer.get_model", side_effect=[chooser_model, preselector_model]):
        loop = _chooser_config(preselector=True).get_retry_loop(TextProblemStatement(text="fix the bug"))
        for cost in (1.0, 1.0, 1.0):
            loop.on_submit(_submission(cost))
        loop.get_best()

    assert loop.review_model_stats == InstanceStats(instance_cost=3.5, api_calls=2)
    assert loop._total_stats == InstanceStats(instance_cost=6.5, api_calls=5)
