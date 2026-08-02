import pytest

import sweagent.agent.reviewer as reviewer_module
from sweagent.agent.models import InstanceStats, InstantEmptySubmitModelConfig
from sweagent.agent.problem_statement import TextProblemStatement
from sweagent.agent.reviewer import (
    ChooserConfig,
    ChooserRetryLoopConfig,
    PreselectorConfig,
    ReviewSubmission,
)


class FakeModel:
    def __init__(self, stats: InstanceStats):
        self.stats = stats

    def query(self, _messages: list[dict[str, str]]) -> dict[str, str]:
        return {"message": "0"}


@pytest.fixture
def chooser_config() -> ChooserRetryLoopConfig:
    model = InstantEmptySubmitModelConfig()
    return ChooserRetryLoopConfig(
        chooser=ChooserConfig(
            model=model,
            system_template="choose",
            instance_template="{{ problem_statement }}",
            submission_template="{{ submission }}",
            preselector=PreselectorConfig(
                model=model,
                system_template="preselect",
                instance_template="{{ problem_statement }}",
                submission_template="{{ submission }}",
            ),
        ),
        max_attempts=2,
        cost_limit=10.0,
    )


def test_chooser_retry_loop_reports_chooser_and_preselector_costs(
    monkeypatch: pytest.MonkeyPatch, chooser_config: ChooserRetryLoopConfig
) -> None:
    models = [
        FakeModel(InstanceStats(instance_cost=2.0, tokens_sent=20, api_calls=1)),
        FakeModel(InstanceStats(instance_cost=3.0, tokens_sent=30, api_calls=1)),
    ]
    model_iter = iter(models)
    monkeypatch.setattr(reviewer_module, "get_model", lambda *_args: next(model_iter))

    loop = chooser_config.get_retry_loop(TextProblemStatement(text="fix the bug"))
    for _ in range(3):
        loop.on_submit(
            ReviewSubmission(
                trajectory=[],
                info={"submission": "pass", "exit_status": "submitted"},
                model_stats=InstanceStats(instance_cost=4.0),
            )
        )
    loop.get_best()

    assert loop.review_model_stats == InstanceStats(instance_cost=5.0, tokens_sent=50, api_calls=2)
    assert loop._total_stats == InstanceStats(instance_cost=12.0)
