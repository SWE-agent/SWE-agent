"""End-to-end tests for the Anthropic `str_replace_editor` tool.

The tool is a standalone script that persists state to the registry file between
(separate-process) invocations, so we exercise it as a subprocess.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sweagent import TOOLS_DIR

EDITOR = TOOLS_DIR / "edit_anthropic" / "bin" / "str_replace_editor"
REGISTRY_LIB = TOOLS_DIR / "registry" / "lib"


def _run_editor(args: list[str], env_file: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["SWE_AGENT_ENV_FILE"] = str(env_file)
    env["PYTHONPATH"] = str(REGISTRY_LIB) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, str(EDITOR), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_undo_edit_restores_previous_content(tmp_path):
    """Regression test: file history was mutated on the object returned by the
    `_file_history` getter, which never triggered the setter, so nothing was
    persisted and `undo_edit` always failed with "No edit history found"."""
    env_file = tmp_path / ".swe-agent-env"
    env_file.write_text("{}")
    target = tmp_path / "a.py"

    r = _run_editor(["create", str(target), "--file_text", "x = 1\n"], env_file)
    assert r.returncode == 0, r.stdout + r.stderr

    r = _run_editor(["str_replace", str(target), "--old_str", "x = 1", "--new_str", "x = 2"], env_file)
    assert r.returncode == 0, r.stdout + r.stderr
    assert target.read_text() == "x = 2\n"

    # Before the fix this exited 18 ("No edit history found") and left the file unchanged.
    r = _run_editor(["undo_edit", str(target)], env_file)
    assert r.returncode == 0, r.stdout + r.stderr
    assert target.read_text() == "x = 1\n"
