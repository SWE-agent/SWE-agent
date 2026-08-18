from __future__ import annotations

from sweagent.types import AgentInfo, Trajectory


class RetryAgentHook:
    """Observe retry-attempt boundaries without depending on RetryAgent internals."""

    def on_attempt_start(self, *, attempt_index: int, agent_name: str) -> None:
        """Called after a child agent is set up. ``attempt_index`` is zero-based."""

    def on_attempt_done(self, *, attempt_index: int, trajectory: Trajectory, info: AgentInfo) -> None:
        """Called after an attempt's trajectory and statistics are finalized."""


class CombinedRetryAgentHook(RetryAgentHook):
    def __init__(self, hooks: list[RetryAgentHook] | None = None):
        self._hooks = hooks or []

    def add_hook(self, hook: RetryAgentHook) -> None:
        self._hooks.append(hook)

    def on_attempt_start(self, *, attempt_index: int, agent_name: str) -> None:
        for hook in self._hooks:
            hook.on_attempt_start(attempt_index=attempt_index, agent_name=agent_name)

    def on_attempt_done(self, *, attempt_index: int, trajectory: Trajectory, info: AgentInfo) -> None:
        for hook in self._hooks:
            hook.on_attempt_done(attempt_index=attempt_index, trajectory=trajectory, info=info)
