import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from sweagent.agent.problem_statement import EmptyProblemStatement
from sweagent.environment.swe_env import SWEEnv
from sweagent.run import run_single
from sweagent.run.hooks.abstract import RunHook
from sweagent.types import AgentRunResult


class _PrimaryFailure(ValueError):
    pass


class _CleanupFailure(RuntimeError):
    pass


class _OfflineRuntime:
    def __init__(self, startup_error=None):
        self.startup_error = startup_error

    async def create_session(self, request):
        if self.startup_error is not None:
            raise self.startup_error
        return SimpleNamespace()

    async def run_in_session(self, request):
        failed = request.command == "controlled-failure"
        return SimpleNamespace(output="controlled failure" if failed else "", exit_code=int(failed))


class _OfflineDeployment:
    def __init__(self, *, startup_error=None, cleanup_error=None, fail_stop_from=1):
        self.runtime = _OfflineRuntime(startup_error)
        self.cleanup_error = cleanup_error
        self.fail_stop_from = fail_stop_from
        self.start_calls = 0
        self.stop_calls = 0
        self.running = False

    async def start(self):
        self.start_calls += 1
        self.running = True

    async def stop(self):
        self.stop_calls += 1
        self.running = False
        if self.cleanup_error is not None and self.stop_calls >= self.fail_stop_from:
            raise self.cleanup_error


class _OfflineAgent:
    replay_config = None

    def __init__(self, *, primary=None, communicate_failure=False):
        self.primary = primary
        self.communicate_failure = communicate_failure
        self.run_calls = 0

    def run(self, *, env, **kwargs):
        self.run_calls += 1
        if self.communicate_failure:
            try:
                env.communicate("controlled-failure", check="raise")
            except RuntimeError as error:
                self.primary = error
                raise
        if self.primary is not None:
            raise self.primary
        return AgentRunResult(info={"exit_status": "submitted", "submission": ""}, trajectory=[])


class _InjectionHook(RunHook):
    def __init__(self, stage, primary):
        self.stage = stage
        self.primary = primary

    def on_start(self):
        if self.stage == "before_start":
            raise self.primary

    def on_instance_start(self, **kwargs):
        if self.stage == "hook_start":
            raise self.primary

    def on_instance_completed(self, **kwargs):
        if self.stage == "hook_complete":
            raise self.primary


class TestRunSingleCleanup(unittest.TestCase):
    def setUp(self):
        # Keep the runner alive so deployment destruction cannot hide missing cleanup.
        self.retained = []

    def make_run(self, output_dir, *, stage=None, primary=None, cleanup_error=None, fail_stop_from=1):
        deployment = _OfflineDeployment(
            startup_error=primary if stage == "startup" else None,
            cleanup_error=cleanup_error,
            fail_stop_from=fail_stop_from,
        )
        env = SWEEnv(deployment=deployment, repo=None, post_startup_commands=[])
        agent = _OfflineAgent(primary=primary if stage == "agent" else None, communicate_failure=stage == "communicate")
        run = run_single.RunSingle(
            env=env,
            agent=agent,
            problem_statement=EmptyProblemStatement(id="offline-lifecycle"),
            output_dir=Path(output_dir),
            hooks=[_InjectionHook(stage, primary)],
        )
        self.retained.append((run, env, deployment, agent))
        return run, deployment, agent

    def test_failures_close_environment_and_preserve_original_exception(self):
        for stage, cleanup_fails in [
            ("hook_start", False),
            ("agent", False),
            ("hook_complete", False),
            ("save", False),
            ("startup", False),
            ("agent", True),
        ]:
            with self.subTest(stage=stage, cleanup_fails=cleanup_fails):
                with tempfile.TemporaryDirectory() as directory:
                    primary = _PrimaryFailure(stage)
                    cleanup = _CleanupFailure("secondary cleanup") if cleanup_fails else None
                    run, deployment, _ = self.make_run(directory, stage=stage, primary=primary, cleanup_error=cleanup)
                    with ExitStack() as injection:
                        if stage == "save":
                            injection.enter_context(patch.object(run_single, "save_predictions", side_effect=primary))
                        with pytest.raises(_PrimaryFailure) as caught:
                            run.run()
                    assert caught.value is primary
                    assert deployment.start_calls == 1
                    assert deployment.stop_calls == 1
                    assert not deployment.running

    def test_failure_before_start_does_not_close_unstarted_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            primary = _PrimaryFailure("before start")
            run, deployment, _ = self.make_run(directory, stage="before_start", primary=primary)
            with pytest.raises(_PrimaryFailure) as caught:
                run.run()
            assert caught.value is primary
            assert deployment.start_calls == 0
            assert deployment.stop_calls == 0

    def test_process_exit_exceptions_close_and_propagate(self):
        for primary in [KeyboardInterrupt("interrupted"), SystemExit(7)]:
            with self.subTest(exception=type(primary).__name__):
                with tempfile.TemporaryDirectory() as directory:
                    run, deployment, _ = self.make_run(directory, stage="agent", primary=primary)
                    with pytest.raises(type(primary)) as caught:
                        run.run()
                    assert caught.value is primary
                    assert deployment.stop_calls == 1
                    assert not deployment.running

    def test_communicate_failure_preserves_error_after_environment_already_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            cleanup = _CleanupFailure("already stopped")
            run, deployment, agent = self.make_run(
                directory, stage="communicate", cleanup_error=cleanup, fail_stop_from=2
            )
            with pytest.raises(RuntimeError) as caught:
                run.run()
            assert caught.value is agent.primary
            assert caught.value is not cleanup
            assert deployment.stop_calls == 2
            assert not deployment.running

    def test_success_closes_and_saves_prediction(self):
        with tempfile.TemporaryDirectory() as directory:
            run, deployment, agent = self.make_run(directory)
            run.run()
            assert agent.run_calls == 1
            assert deployment.stop_calls == 1
            assert not deployment.running
            assert (Path(directory) / "offline-lifecycle/offline-lifecycle.pred").is_file()

    def test_cleanup_only_failure_remains_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            cleanup = _CleanupFailure("cleanup only")
            run, deployment, _ = self.make_run(directory, cleanup_error=cleanup)
            with pytest.raises(_CleanupFailure) as caught:
                run.run()
            assert caught.value is cleanup
            assert deployment.stop_calls == 1


if __name__ == "__main__":
    unittest.main()
