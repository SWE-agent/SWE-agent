from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from sweagent.exceptions import FormatError
from sweagent.run.inspector_cli import main as inspector_main
from sweagent.tools.validation import validate_path


def test_absolute_path_outside_workspace():
    """R1: Check that absolute paths outside the workspace raise FormatError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir).resolve()
        
        # An absolute path that is outside the workspace
        outside_path = Path("/etc/passwd")
        # On Windows, /etc/passwd might resolve to C:\etc\passwd or similar. Make sure it's outside workspace.
        if outside_path.is_absolute() and not outside_path.is_relative_to(workspace):
            with pytest.raises(FormatError):
                validate_path(str(outside_path), workspace)

        # Test with a guaranteed different directory
        with tempfile.TemporaryDirectory() as other_tmpdir:
            other_workspace = Path(other_tmpdir).resolve()
            with pytest.raises(FormatError):
                validate_path(str(other_workspace / "some_file.txt"), workspace)


def test_relative_path_escape_workspace():
    """R1: Check that relative paths that escape the workspace raise FormatError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir).resolve()
        escape_path = "../../etc/passwd"
        with pytest.raises(FormatError):
            validate_path(escape_path, workspace)


def test_non_existent_file_for_read_edit():
    """R1: Check that relative or absolute paths to non-existent files for reading/editing raise FormatError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir).resolve()
        non_existent = "missing_file.txt"
        with pytest.raises(FormatError):
            validate_path(non_existent, workspace, is_create=False)


def test_create_file_non_existent_parent_exists():
    """R1: Check that create tools succeed even if the file does not exist, provided it is inside the workspace and its parent directory exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir).resolve()
        new_file = "new_file.txt"
        resolved = validate_path(new_file, workspace, is_create=True)
        assert resolved == workspace / new_file


def test_create_file_parent_not_exists():
    """R1: Check that create tools fail if the parent directory does not exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir).resolve()
        new_file = "non_existent_dir/new_file.txt"
        with pytest.raises(FormatError):
            validate_path(new_file, workspace, is_create=True)


def test_valid_file_inside_workspace():
    """R1: Check that valid file paths inside the workspace are allowed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir).resolve()
        valid_file = workspace / "valid.txt"
        valid_file.write_text("hello")
        
        # Valid path inside workspace
        resolved = validate_path("valid.txt", workspace, is_create=False)
        assert resolved == valid_file
        
        # Absolute valid path inside workspace
        resolved_abs = validate_path(str(valid_file), workspace, is_create=False)
        assert resolved_abs == valid_file


def test_trajectory_analyzer_cli(tmp_path):
    """R2: Run trajectory analyzer CLI tool using subprocess and verify generated reports."""
    output_md = tmp_path / "report.md"
    output_json = tmp_path / "report.json"
    
    script_path = Path(__file__).resolve().parent.parent / "sweagent" / "utils" / "trajectory_analyzer.py"
    
    cmd = [
        sys.executable,
        str(script_path),
        "--directory", "tests/test_data/trajectories",
        "--output-markdown", str(output_md),
        "--output-json", str(output_json)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    assert output_md.exists()
    assert output_json.exists()
    
    # Check JSON metrics content
    metrics = json.loads(output_json.read_text())
    assert "total_cost" in metrics
    assert "total_api_calls" in metrics
    assert "total_tokens" in metrics
    assert "exit_status_distribution" in metrics
    
    assert isinstance(metrics["total_cost"], float)
    assert isinstance(metrics["total_api_calls"], int)
    assert isinstance(metrics["total_tokens"], int)
    assert isinstance(metrics["exit_status_distribution"], dict)
    
    # Check Markdown report content
    md_content = output_md.read_text()
    assert "# Trajectory Analysis Summary Report" in md_content
    assert "Total Cost (USD)" in md_content
    assert "Total API Calls" in md_content
    assert "Exit Status Distribution" in md_content


def test_inspector_cli_data_path_bug():
    """R2/inspector_cli.py: Test that data_path is passed to TrajectoryInspectorApp when using CLI arguments."""
    with patch("sweagent.run.inspector_cli.TrajectoryInspectorApp") as mock_app:
        inspector_main(["tests/test_data/trajectories", "--data_path", "tests/test_data/data_sources/human_eval.json"])
        mock_app.assert_called_once_with(
            "tests/test_data/trajectories",
            data_path=Path("tests/test_data/data_sources/human_eval.json")
        )


def test_inspector_cli_data_path_bug_short_option():
    """R2/inspector_cli.py: Test that data_path is passed to TrajectoryInspectorApp when using CLI short argument -d."""
    with patch("sweagent.run.inspector_cli.TrajectoryInspectorApp") as mock_app:
        inspector_main(["tests/test_data/trajectories", "-d", "tests/test_data/data_sources/human_eval.json"])
        mock_app.assert_called_once_with(
            "tests/test_data/trajectories",
            data_path=Path("tests/test_data/data_sources/human_eval.json")
        )


def test_agent_validate_step_action():
    """R1: Test that DefaultAgent._validate_step_action correctly validates step actions."""
    from unittest.mock import MagicMock
    from sweagent.agent.agents import DefaultAgent
    from sweagent.types import StepOutput

    mock_templates = MagicMock()
    mock_tools = MagicMock()
    mock_history_processors = []
    mock_model = MagicMock()

    agent = DefaultAgent(
        templates=mock_templates,
        tools=mock_tools,
        history_processors=mock_history_processors,
        model=mock_model,
    )
    
    with patch("sweagent.agent.agents.validate_path") as mock_val_path:
        # Test text parsing view_file
        step = StepOutput(action="view_file path/to/file.py")
        agent._validate_step_action(step, {})
        mock_val_path.assert_called_with("path/to/file.py", "/", is_create=False, env=agent._env)

        # Test text parsing create
        step = StepOutput(action="create path/to/file.py")
        agent._validate_step_action(step, {})
        mock_val_path.assert_called_with("path/to/file.py", "/", is_create=True, env=agent._env)

        # Test tool calling view_file
        step = StepOutput(action="")
        output = {
            "tool_calls": [
                {
                    "function": {
                        "name": "view_file",
                        "arguments": '{"path": "path/to/file2.py"}'
                    }
                }
            ]
        }
        agent._validate_step_action(step, output)
        mock_val_path.assert_called_with("path/to/file2.py", "/", is_create=False, env=agent._env)

        # Test tool calling str_replace_editor create
        output = {
            "tool_calls": [
                {
                    "function": {
                        "name": "str_replace_editor",
                        "arguments": '{"command": "create", "path": "path/to/file3.py"}'
                    }
                }
            ]
        }
        agent._validate_step_action(step, output)
        mock_val_path.assert_called_with("path/to/file3.py", "/", is_create=True, env=agent._env)

