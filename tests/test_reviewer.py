from __future__ import annotations

import pytest

from sweagent.agent.models import AbstractModel, GenericAPIModelConfig, InstanceStats
from sweagent.agent.reviewer import (
    Chooser,
    ChooserConfig,
    Preselector,
    PreselectorConfig,
    ReviewSubmission,
)
from sweagent.exceptions import (
    InstanceCostLimitExceededError,
    TotalCostLimitExceededError,
)
from sweagent.utils.log import get_logger


class _RaisingModel(AbstractModel):
    """A model whose every query fails with a fixed exception."""

    def __init__(self, exc: Exception):
        self._exc = exc

    def query(self, *args, **kwargs):
        raise self._exc

    @property
    def stats(self) -> InstanceStats:
        return InstanceStats()


class _ConstantModel(AbstractModel):
    """A model that always answers with the same message."""

    def __init__(self, message: str):
        self._message = message

    def query(self, *args, **kwargs):
        return {"message": self._message}

    @property
    def stats(self) -> InstanceStats:
        return InstanceStats()


def _chooser(model: AbstractModel, *, preselector: PreselectorConfig | None = None) -> Chooser:
    config = ChooserConfig(
        model=GenericAPIModelConfig(name="test-model"),
        system_template="system",
        instance_template="instance {{problem_statement}}",
        submission_template="submission {{submission}}",
        preselector=preselector,
    )
    # Bypass __init__ so that no real model is instantiated.
    chooser = object.__new__(Chooser)
    chooser.config = config
    chooser.logger = get_logger("test-chooser")
    chooser.model = model
    return chooser


def _submission() -> ReviewSubmission:
    return ReviewSubmission(
        submission="solution text",
        trajectory=[],
        info={"exit_status": "submitted", "submission": "solution text", "model_stats": {}},
        model_stats=InstanceStats(),
    )


@pytest.mark.parametrize("exc_type", [TotalCostLimitExceededError, InstanceCostLimitExceededError])
def test_chooser_propagates_cost_limit_errors(exc_type):
    """A cost limit hit by the chooser model must abort, not be swallowed."""
    chooser = _chooser(_RaisingModel(exc_type("cost limit")))
    with pytest.raises(exc_type):
        chooser.choose("problem statement", [_submission(), _submission()])


def test_chooser_falls_back_when_query_fails():
    """Any other query failure keeps the graceful fallback (no UnboundLocalError)."""
    chooser = _chooser(_RaisingModel(RuntimeError("boom")))
    output = chooser.choose("problem statement", [_submission(), _submission()])
    assert output.chosen_idx == 0
    assert output.response == ""


def test_chooser_returns_chosen_index():
    chooser = _chooser(_ConstantModel("I choose submission 1"))
    output = chooser.choose("problem statement", [_submission(), _submission()])
    assert output.chosen_idx == 1


@pytest.mark.parametrize("exc_type", [TotalCostLimitExceededError, InstanceCostLimitExceededError])
def test_preselector_cost_limit_propagates_through_chooser(exc_type, monkeypatch):
    """The same holds for a cost limit raised by the preselector model."""
    preselector_config = PreselectorConfig(
        model=GenericAPIModelConfig(name="test-model"),
        system_template="system",
        instance_template="instance {{problem_statement}}",
        submission_template="submission {{submission}}",
    )

    def _fake_init(self, config):
        self.config = config
        self.logger = get_logger("test-preselector")
        self.model = _RaisingModel(exc_type("cost limit"))

    monkeypatch.setattr(Preselector, "__init__", _fake_init)
    chooser = _chooser(_ConstantModel("I choose submission 0"), preselector=preselector_config)
    with pytest.raises(exc_type):
        chooser.choose("problem statement", [_submission(), _submission(), _submission()])
