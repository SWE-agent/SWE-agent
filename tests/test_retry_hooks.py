from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sweagent.agent.agents import DefaultAgent, DefaultAgentConfig, RetryAgent, RetryAgentConfig, TemplateConfig
from sweagent.agent.hooks.retry import CombinedRetryAgentHook, RetryAgentHook
from sweagent.agent.models import InstanceStats, InstantEmptySubmitModelConfig
from sweagent.agent.reviewer import ChooserConfig, ChooserRetryLoopConfig


class RecordingRetryHook(RetryAgentHook):
    def __init__(self):
        self.events: list[tuple[str, int, Any]] = []

    def on_attempt_start(self, *, attempt_index: int, agent_name: str) -> None:
        self.events.append(("start", attempt_index, agent_name))

    def on_attempt_done(self, *, attempt_index: int, trajectory, info) -> None:
        self.events.append(("done", attempt_index, (trajectory, info)))


def test_combined_retry_hook_forwards_attempt_lifecycle():
    first = RecordingRetryHook()
    second = RecordingRetryHook()
    hooks = CombinedRetryAgentHook([first, second])
    trajectory = [{"action": "submit", "observation": "", "response": ""}]
    info = {"exit_status": "submitted"}

    hooks.on_attempt_start(attempt_index=0, agent_name="main")
    hooks.on_attempt_done(attempt_index=0, trajectory=trajectory, info=info)

    expected = [
        ("start", 0, "main"),
        ("done", 0, (trajectory, info)),
    ]
    assert first.events == expected
    assert second.events == expected


def test_retry_agent_emits_attempt_events_after_setup_and_finalization(tmp_path, monkeypatch):
    attempt_config = DefaultAgentConfig(
        name="attempt-agent",
        model=InstantEmptySubmitModelConfig(),
        templates=TemplateConfig(system_template="system", instance_template="instance"),
    )
    retry_config = RetryAgentConfig(
        agent_configs=[attempt_config],
        retry_loop=ChooserRetryLoopConfig(
            chooser=ChooserConfig(
                model=InstantEmptySubmitModelConfig(),
                system_template="",
                instance_template="",
                submission_template="",
            ),
            max_attempts=1,
            cost_limit=1.0,
        ),
    )
    trajectory = [{"action": "submit"}]
    info = {"exit_status": "submitted"}

    class FakeAttemptAgent:
        name = "attempt-agent"
        model = SimpleNamespace(stats=InstanceStats())

        def __init__(self):
            self.trajectory = trajectory
            self.info = info

        def setup(self, **kwargs):
            self.setup_kwargs = kwargs

        def save_trajectory(self):
            pass

        def get_trajectory_data(self):
            return {"trajectory": self.trajectory, "info": self.info}

    monkeypatch.setattr(DefaultAgent, "from_config", lambda config: FakeAttemptAgent())
    agent = RetryAgent(retry_config)
    agent._problem_statement = object()  # type: ignore[assignment]
    agent._env = object()  # type: ignore[assignment]
    agent._output_dir = tmp_path
    agent._rloop = SimpleNamespace(review_model_stats=InstanceStats())  # type: ignore[assignment]
    hook = RecordingRetryHook()
    agent.add_retry_hook(hook)

    agent._setup_agent()
    agent._finalize_agent_run()

    assert hook.events == [
        ("start", 0, "attempt-agent"),
        ("done", 0, (trajectory, info)),
    ]
