from __future__ import annotations

import base64
from pathlib import Path
from unittest import mock

import pytest
from swerex.exceptions import CommandTimeoutError
from swerex.runtime.abstract import Command, CommandResponse
from swerex.runtime.dummy import DummyRuntime

from sweagent.environment.hooks.abstract import EnvHook

from .conftest import swe_env_context


@pytest.mark.slow
def test_init_swe_env(test_env_args):
    with swe_env_context(test_env_args):
        pass


@pytest.mark.slow
def test_init_swe_env_conservative_clone(test_env_args):
    with mock.patch.dict("os.environ", {"SWE_AGENT_CLONE_METHOD": "full"}):
        with swe_env_context(test_env_args):
            pass


@pytest.mark.slow
def test_startup_commands(test_env_args):
    test_script = "echo 'hello world'"
    test_env_args.post_startup_commands = [test_script]
    with swe_env_context(test_env_args):
        pass


@pytest.mark.xfail
@pytest.mark.slow
def test_read_file(tmp_path, test_env_args):
    with swe_env_context(test_env_args) as env:
        content = env.read_file(Path("tests/filetoread.txt"))
        assert content.splitlines()[-1].strip() == "SWEEnv.read_file"


def test_read_file_preserve_newlines(dummy_env):
    class BytesRuntime(DummyRuntime):
        def __init__(self):
            super().__init__()
            self.command: Command | None = None

        async def execute(self, command: Command) -> CommandResponse:
            self.command = command
            content = base64.b64encode(b"line1\r\nline2\rline3\n").decode("ascii")
            return CommandResponse(stdout=content, exit_code=0)

    runtime = BytesRuntime()
    dummy_env.deployment.runtime = runtime  # type: ignore[assignment]

    content = dummy_env.read_file("/root/model.patch", encoding="utf-8", preserve_newlines=True)

    assert content == "line1\r\nline2\rline3\n"
    assert runtime.command is not None
    assert runtime.command.command == [
        "python",
        "-c",
        (
            "import base64, pathlib, sys; "
            "sys.stdout.write(base64.b64encode(pathlib.Path(sys.argv[1]).read_bytes()).decode('ascii'))"
        ),
        "/root/model.patch",
    ]


@pytest.mark.slow
def test_env_with_hook(test_env_args):
    with swe_env_context(test_env_args) as env:
        env.add_hook(EnvHook())
        env.reset()


@pytest.mark.slow
def test_env_communicate_with_handling(test_env_args):
    with swe_env_context(test_env_args) as env:
        env.communicate("echo 'hello world'", check="raise", error_msg="Failed to echo")


@pytest.mark.slow
def test_env_communicate_with_handling_timeout(test_env_args):
    with swe_env_context(test_env_args) as env:
        with pytest.raises(CommandTimeoutError):
            env.communicate("sleep 10", check="raise", error_msg="Failed to sleep", timeout=0.2)


@pytest.mark.slow
def test_env_interrupt_session(test_env_args):
    with swe_env_context(test_env_args) as env:
        env.interrupt_session()
