from __future__ import annotations

import json
import tempfile
from pathlib import Path

from sweagent.run.quick_stats import quick_stats


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
