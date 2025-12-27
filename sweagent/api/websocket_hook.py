"""WebSocket hook for SWE-agent that emits real-time updates during execution."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from sweagent.agent.hooks.abstract import AbstractAgentHook

if TYPE_CHECKING:
    from sweagent.types import AgentInfo, StepOutput


class WebSocketHook(AbstractAgentHook):
    """Agent hook that emits updates via WebSocket during agent execution."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.lock = threading.Lock()
        # Store trajectory steps to emit them later
        self.trajectory_steps = []

    def on_init(self, *, agent):
        """Initialize the hook."""
        pass

    def on_run_start(self):
        """Called when the agent run starts."""
        self._emit_update("run_start", {
            "status": "running",
            "step_count": 0,
            "message": "Agent execution started",
        })

    def on_step_start(self):
        """Called when a step starts."""
        # Emit update to indicate step started
        self._emit_update("step_start", {
            "status": "running",
            "message": "Starting new step...",
        })

    def on_actions_generated(self, *, step: StepOutput):
        """Called when actions are generated."""
        # Emit update to indicate actions are being planned
        if step.thought:
            self._emit_update("actions_planned", {
                "status": "running",
                "message": f"Planning: {step.thought[:100]}..." if len(step.thought) > 100 else step.thought,
            })

    def on_action_started(self, *, step: StepOutput):
        """Called when an action starts execution."""
        # Emit update to indicate action is starting
        if step.action:
            self._emit_update("action_start", {
                "status": "running",
                "message": f"Executing: {step.action[:100]}..." if len(step.action) > 100 else step.action,
            })

    def on_action_executed(self, *, step: StepOutput):
        """Called when an action is executed."""
        pass

    def on_step_done(self, *, step: StepOutput, info: AgentInfo):
        """Called when a step is completed."""
        # Store the current step information for later emission
        with self.lock:
            trajectory_step = {
                "action": step.action,
                "observation": step.observation,
                "response": step.output,
                "thought": step.thought,
                "execution_time": step.execution_time,
                "state": step.state,
                "query": step.query,
                "extra_info": step.extra_info,
            }
            self.trajectory_steps.append(trajectory_step)
        
        # Emit update with current step count, info, and the actual step details
        step_count = len(self.trajectory_steps) if self.trajectory_steps else 0
        self._emit_update("step_complete", {
            "status": "running",
            "step_count": step_count,
            "exit_status": info.get("exit_status"),
            "model_stats": info.get("model_stats", {}),
            "current_step": trajectory_step,  # Include the actual step details
        })

    def on_run_done(self, *, trajectory: Any, info: "AgentInfo"):
        """Called when the agent run is completed."""
        # Emit final update with complete trajectory
        step_count = len(trajectory) if isinstance(trajectory, list) else 0
        self._emit_update("run_complete", {
            "status": "completed",
            "step_count": step_count,
            "exit_status": info.get("exit_status"),
            "model_stats": info.get("model_stats", {}),
        })

    def on_setup_attempt(self):
        """Called when setting up an attempt."""
        pass

    def on_model_query(self, *, messages: list[dict[str, str]], agent: str):
        """Called when querying the model."""
        pass

    def on_query_message_added(
        self,
        *,
        agent: str,
        role: str,
        content: str,
        message_type: str,
        is_demo: bool = False,
        thought: str = "",
        action: str = "",
        tool_calls: list[dict[str, str]] | None = None,
        tool_call_ids: list[str] | None = None,
    ):
        """Called when a query message is added."""
        pass

    def on_setup_done(self):
        """Called when setup is done."""
        pass

    def on_tools_installation_started(self):
        """Called when tools installation starts."""
        pass

    def _emit_update(self, event: str, data: Any):
        """Emit an update via the global emit function."""
        # This will be set by the server when the hook is used
        if hasattr(self, '_emit_function'):
            self._emit_function(self.run_id, event, data)

    def get_trajectory_steps(self) -> list[dict[str, Any]]:
        """Get the collected trajectory steps."""
        with self.lock:
            return self.trajectory_steps.copy()