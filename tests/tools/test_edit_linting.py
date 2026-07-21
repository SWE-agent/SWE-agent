from __future__ import annotations

import json
from unittest import mock

from sweagent import TOOLS_DIR
from tests.utils import make_python_tool_importable

make_python_tool_importable(TOOLS_DIR / "windowed_edit_linting" / "bin" / "edit", "windowed_edit_linting_edit")
import windowed_edit_linting_edit  # type: ignore  # noqa: E402


def _setup_file(env_file, content: str):
    test_path = env_file.parent / "test.py"
    test_path.write_text(content)
    env_file.write_text(json.dumps({"CURRENT_FILE": str(test_path), "FIRST_LINE": "0", "WINDOW": "50"}))
    return test_path


def test_preexisting_error_above_edit_does_not_revert(with_tmp_env_file):
    """Regression test: the flake8 filter window was passed 0-based while flake8
    line numbers are 1-based, so a pre-existing error on the line directly above
    the edited region was misclassified as newly introduced and the (valid) edit
    was reverted."""
    # 15-line file; the (mocked) pre-existing lint error lives on 1-based line 4,
    # i.e. directly above the 1-based lines 5-10 that we edit.
    path = _setup_file(with_tmp_env_file, "\n".join(f"line{i}" for i in range(1, 16)) + "\n")
    preexisting = f"{path}:4:1: F821 undefined name 'x'"

    # flake8 returns the same pre-existing error before and after the edit.
    with mock.patch.object(windowed_edit_linting_edit, "flake8", return_value=preexisting):
        windowed_edit_linting_edit.main("5:10", "REPLACED")

    # The edit must have been applied rather than reverted by a bogus lint error.
    assert "REPLACED" in path.read_text()
