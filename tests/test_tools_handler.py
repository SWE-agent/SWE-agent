from __future__ import annotations

from sweagent.tools.tools import ToolConfig, ToolHandler


class _RecordingEnv:
    """Minimal stand-in for `SWEEnv` that records what `ToolHandler.reset` sends."""

    def __init__(self):
        self.env_variables: dict[str, object] = {}
        self.written_files: dict[str, str] = {}
        self.commands: list[str] = []

    def set_env_variables(self, env_variables: dict[str, object]) -> None:
        self.env_variables = env_variables

    def write_file(self, path: str, content: str) -> None:
        self.written_files[str(path)] = content

    def communicate(self, input: str, check: str = "ignore", timeout: int | float = 25) -> str:
        self.commands.append(input)
        return ""


def test_reset_only_propagates_variables_that_are_set(monkeypatch):
    """Unset host variables must not be forwarded to the environment.

    `SWEEnv.set_env_variables` renders `str(value)` into `export var=value`, so forwarding an
    unset variable would export the literal string "None".
    """
    monkeypatch.delenv("SWE_AGENT_TEST_UNSET_TOKEN", raising=False)
    monkeypatch.setenv("SWE_AGENT_TEST_SET_TOKEN", "s3cret")
    config = ToolConfig(propagate_env_variables=["SWE_AGENT_TEST_UNSET_TOKEN", "SWE_AGENT_TEST_SET_TOKEN"])
    env = _RecordingEnv()

    ToolHandler(config).reset(env)  # type: ignore[arg-type]

    assert env.env_variables["SWE_AGENT_TEST_SET_TOKEN"] == "s3cret"
    assert "SWE_AGENT_TEST_UNSET_TOKEN" not in env.env_variables
    assert all(value is not None for value in env.env_variables.values())
