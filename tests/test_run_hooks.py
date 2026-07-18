import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest

from sweagent.agent.problem_statement import GithubIssue, TextProblemStatement
from sweagent.run.hooks.apply_patch import SaveApplyPatchHook
from sweagent.run.hooks.open_pr import OpenPRConfig, OpenPRHook
from sweagent.run.hooks.swe_bench_evaluate import SweBenchEvaluate
from sweagent.run.hooks.trajectory import SaveTrajectoryHook
from sweagent.types import AgentRunResult


@pytest.fixture
def open_pr_hook_init_for_sop():
    hook = OpenPRHook(config=OpenPRConfig(skip_if_commits_reference_issue=True))
    hook._token = os.environ.get("GITHUB_TOKEN", "")
    hook._problem_statement = GithubIssue(github_url="https://github.com/swe-agent/test-repo/issues/1")
    return hook


@pytest.fixture
def agent_run_result():
    return AgentRunResult(
        info={
            "submission": "asdf",
            "exit_status": "submitted",
        },
        trajectory=[],
    )


def test_should_open_pr_fail_submission(open_pr_hook_init_for_sop, agent_run_result):
    hook = open_pr_hook_init_for_sop
    agent_run_result.info["submission"] = None
    assert not hook.should_open_pr(agent_run_result)


def test_should_open_pr_fail_exit(open_pr_hook_init_for_sop, agent_run_result):
    hook = open_pr_hook_init_for_sop
    agent_run_result.info["exit_status"] = "fail"
    assert not hook.should_open_pr(agent_run_result)


def test_should_open_pr_fail_invalid_url(open_pr_hook_init_for_sop, agent_run_result):
    hook = open_pr_hook_init_for_sop
    agent_run_result.info["data_path"] = "asdf"
    assert not hook.should_open_pr(agent_run_result)


def test_should_open_pr_fail_closed(open_pr_hook_init_for_sop, agent_run_result):
    hook = open_pr_hook_init_for_sop
    hook._problem_statement = GithubIssue(github_url="https://github.com/swe-agent/test-repo/issues/16")
    assert not hook.should_open_pr(agent_run_result)


def test_should_open_pr_fail_assigned(open_pr_hook_init_for_sop, agent_run_result):
    hook = open_pr_hook_init_for_sop
    hook._problem_statement = GithubIssue(github_url="https://github.com/swe-agent/test-repo/issues/17")
    assert not hook.should_open_pr(agent_run_result)


def test_should_open_pr_fail_locked(open_pr_hook_init_for_sop, agent_run_result):
    hook = open_pr_hook_init_for_sop
    hook._problem_statement = GithubIssue(github_url="https://github.com/swe-agent/test-repo/issues/18")
    assert not hook.should_open_pr(agent_run_result)


def test_should_open_pr_fail_has_pr(open_pr_hook_init_for_sop, agent_run_result):
    hook = open_pr_hook_init_for_sop
    hook._problem_statement = GithubIssue(github_url="https://github.com/swe-agent/test-repo/issues/19")
    assert not hook.should_open_pr(agent_run_result)


def test_should_open_pr_success_has_pr_override(open_pr_hook_init_for_sop, agent_run_result):
    hook = open_pr_hook_init_for_sop
    hook._problem_statement = GithubIssue(github_url="https://github.com/swe-agent/test-repo/issues/19")
    hook._config.skip_if_commits_reference_issue = False
    assert hook.should_open_pr(agent_run_result)


def test_save_apply_patch_hook_concurrent_workers_save_to_correct_dirs(tmp_path):
    """Regression test for #1284: concurrent workers must not overwrite each
    other's per-instance state (_problem_statement, _env) in SaveApplyPatchHook.

    Before the fix, a single shared hook instance stored _problem_statement as a
    plain instance attribute.  When two workers both called on_instance_start()
    before either finished, the second write overwrote the first, causing both
    workers to save their patch into the same (wrong) output directory.

    The fix uses threading.local() so every worker thread sees its own copy.
    """
    hook = SaveApplyPatchHook(show_success_message=False)
    hook._output_dir = tmp_path

    # Barrier ensures both workers have called on_instance_start before either
    # proceeds to on_instance_completed, making the race window deterministic.
    barrier = threading.Barrier(2)

    def worker(instance_id: str, patch_content: str) -> None:
        ps = TextProblemStatement(text=f"Issue for {instance_id}", id=instance_id)
        env = MagicMock()
        env.repo = None  # skip apply_patch_locally path

        hook.on_instance_start(index=0, env=env, problem_statement=ps)

        # Hold here until both threads have written their problem_statement so
        # that the race window is guaranteed to be open.
        barrier.wait()

        result = AgentRunResult(
            info={"submission": patch_content, "exit_status": "submitted"},
            trajectory=[],
        )
        hook.on_instance_completed(result=result)

    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(worker, "instance-A", "patch A content")
        fb = pool.submit(worker, "instance-B", "patch B content")
        fa.result()
        fb.result()

    patch_a = tmp_path / "instance-A" / "instance-A.patch"
    patch_b = tmp_path / "instance-B" / "instance-B.patch"

    assert patch_a.exists(), "Patch for instance-A was not saved to its own directory"
    assert patch_b.exists(), "Patch for instance-B was not saved to its own directory"
    assert patch_a.read_text() == "patch A content"
    assert patch_b.read_text() == "patch B content"


def test_save_trajectory_hook_saves_result_to_instance_dir(tmp_path):
    hook = SaveTrajectoryHook()
    hook._output_dir = tmp_path

    ps = TextProblemStatement(text="Issue for instance-A", id="instance-A")
    hook.on_instance_start(index=0, env=MagicMock(), problem_statement=ps)
    result = AgentRunResult(
        info={"submission": "patch content", "exit_status": "submitted"},
        trajectory=[],
    )

    hook.on_instance_completed(result=result)

    trajectory_path = tmp_path / "instance-A" / "instance-A.traj"
    assert trajectory_path.exists()
    data = json.loads(trajectory_path.read_text(encoding="utf-8"))
    assert data["info"]["exit_status"] == "submitted"
    assert data["info"]["submission"] == "patch content"
    assert data["trajectory"] == []


def test_save_trajectory_hook_concurrent_workers_save_to_correct_dirs(tmp_path):
    hook = SaveTrajectoryHook()
    hook._output_dir = tmp_path
    barrier = threading.Barrier(2)

    def worker(instance_id: str, exit_status: str) -> None:
        ps = TextProblemStatement(text=f"Issue for {instance_id}", id=instance_id)
        hook.on_instance_start(index=0, env=MagicMock(), problem_statement=ps)
        barrier.wait()
        result = AgentRunResult(
            info={"submission": None, "exit_status": exit_status},
            trajectory=[],
        )
        hook.on_instance_completed(result=result)

    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(worker, "instance-A", "submitted")
        fb = pool.submit(worker, "instance-B", "early_exit")
        fa.result()
        fb.result()

    traj_a = tmp_path / "instance-A" / "instance-A.traj"
    traj_b = tmp_path / "instance-B" / "instance-B.traj"

    assert traj_a.exists(), "Trajectory for instance-A was not saved to its own directory"
    assert traj_b.exists(), "Trajectory for instance-B was not saved to its own directory"
    assert json.loads(traj_a.read_text(encoding="utf-8"))["info"]["exit_status"] == "submitted"
    assert json.loads(traj_b.read_text(encoding="utf-8"))["info"]["exit_status"] == "early_exit"


@pytest.mark.parametrize(
    ("subset", "expected"),
    [
        ("lite", "swe-bench_lite"),
        ("verified", "swe-bench_verified"),
        ("multimodal", "swe-bench-m"),
    ],
)
def test_swe_bench_evaluate_subset_matches_sb_cli(tmp_path, subset, expected):
    """The subset passed to sb-cli must be one of its accepted values.

    sb-cli's ``Subset`` enum only accepts ``swe-bench_lite``, ``swe-bench_verified``
    and ``swe-bench-m``. In particular the multimodal dataset is ``swe-bench-m``,
    not ``swe-bench_multimodal``, so submitting the latter is rejected at the CLI
    boundary and ``--evaluate=True`` fails on a multimodal run.
    """
    hook = SweBenchEvaluate(output_dir=tmp_path, subset=subset, split="dev")
    call = hook._get_sb_call(tmp_path / "preds.json")
    # ["sb-cli", "submit", <subset>, <split>, ...]
    assert call[2] == expected


@pytest.mark.parametrize("subset", ["full", "multilingual"])
def test_swe_bench_evaluate_unsupported_subset_raises_value_error(tmp_path, subset):
    """Subsets with no sb-cli equivalent must fail with a clear error.

    ``full`` and ``multilingual`` are valid ``SWEBenchInstances.subset`` values for
    loading instances, but sb-cli cannot evaluate them. Building the call must raise
    a descriptive ValueError instead of a bare KeyError.
    """
    hook = SweBenchEvaluate(output_dir=tmp_path, subset=subset, split="dev")
    with pytest.raises(ValueError, match=subset):
        hook._get_sb_call(tmp_path / "preds.json")
