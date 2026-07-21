from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
from swerex.exceptions import CommandTimeoutError

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


@pytest.mark.parametrize(
    ("check", "expected_rex_check"),
    [("ignore", "ignore"), ("warn", "silent"), ("raise", "silent")],
)
def test_communicate_maps_check_to_rex_check(check, expected_rex_check):
    """`check="ignore"` must reach swerex as `ignore` (skip exit-code extraction);
    previously `"silent" if check` always selected `silent` since `check` is a
    non-empty string."""
    from sweagent.environment.swe_env import SWEEnv

    captured = {}

    async def fake_run_in_session(action):
        captured["check"] = action.check
        return mock.Mock(output="", exit_code=0)

    deployment = mock.MagicMock()
    deployment.runtime.run_in_session = fake_run_in_session
    env = SWEEnv(deployment=deployment, repo=None, post_startup_commands=[])

    env.communicate("echo 'hello world'", check=check)
    assert captured["check"] == expected_rex_check
