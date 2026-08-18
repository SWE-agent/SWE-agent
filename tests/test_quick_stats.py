from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from sweagent.run.quick_stats import collect_stats, quick_stats


def test_quick_stats_empty_directory():
    """Test that quick_stats handles empty directories properly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        result = quick_stats(tmp_dir)
        assert result == "No .traj files found."


def test_quick_stats_test_data(test_trajectories_path: Path):
    """Test that quick_stats works on the test data directory."""
    # Create a sample .traj file with required structure
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        traj_file = tmp_path / "test.traj"

        # Create a minimal valid .traj file
        traj_data = {"info": {"model_stats": {"api_calls": 42}, "exit_status": "success"}}

        traj_file.write_text(json.dumps(traj_data))

        # Run quick_stats on the directory with our test file
        result = quick_stats(tmp_path)

        # Check that the result contains our exit status
        assert "## `success`" in result

        # Run quick_stats on the test_trajectories_path
        result = quick_stats(test_trajectories_path)

        # The result should not be empty when run on test data
        assert result != "No .traj files found."

        # The result should contain some exit status sections
        assert "## `" in result


def test_collect_stats_returns_machine_readable_summary(tmp_path: Path):
    (tmp_path / "success.traj").write_text(
        json.dumps({"info": {"model_stats": {"api_calls": 2}, "exit_status": "submitted"}})
    )
    (tmp_path / "failed.traj").write_text(
        json.dumps({"info": {"model_stats": {"api_calls": 4}, "exit_status": "exit_cost"}})
    )
    (tmp_path / "invalid.traj").write_text("not json")

    assert collect_stats(tmp_path) == {
        "trajectory_count": 3,
        "valid_trajectory_count": 2,
        "invalid_trajectory_count": 1,
        "average_api_calls": 3.0,
        "exit_status_counts": {"exit_cost": 1, "submitted": 1},
    }


def test_quick_stats_cli_json_output(tmp_path: Path):
    (tmp_path / "test.traj").write_text(
        json.dumps({"info": {"model_stats": {"api_calls": 3}, "exit_status": "submitted"}})
    )

    output = subprocess.run(
        [sys.executable, "-m", "sweagent", "quick-stats", str(tmp_path), "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(output.stdout) == {
        "trajectory_count": 1,
        "valid_trajectory_count": 1,
        "invalid_trajectory_count": 0,
        "average_api_calls": 3.0,
        "exit_status_counts": {"submitted": 1},
    }
