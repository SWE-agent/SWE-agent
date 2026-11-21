"""Tests for `ToolHandler`."""

from __future__ import annotations

from sweagent.tools.tools import ToolConfig, ToolHandler


class _FakeEnv:
    """Records the commands that `ToolHandler` sends to the environment."""

    def __init__(self) -> None:
        self.communicate_calls: list[str] = []
        self.env_variables: dict[str, str] = {}

    def set_env_variables(self, env_variables: dict[str, str]) -> None:
        self.env_variables = env_variables

    def write_file(self, path: str, content: str) -> None:
        pass

    def communicate(self, command: str, **kwargs) -> str:  # noqa: ANN003
        self.communicate_calls.append(command)
        return ""


def test_reset_runs_configured_reset_commands():
    env = _FakeEnv()
    config = ToolConfig(
        reset_commands=[
            "pip install -e .",
            ["export FOO=bar", "source /root/extra.sh"],
        ]
    )
    ToolHandler(config).reset(env)
    assert env.communicate_calls == ["pip install -e . && export FOO=bar && source /root/extra.sh"]
