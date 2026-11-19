import os
import subprocess
import sys
from pathlib import Path

from sweagent import TOOLS_DIR


def _str_replace(path: Path, old_str: str, new_str: str):
    return subprocess.run(
        [
            sys.executable,
            str(TOOLS_DIR / "edit_anthropic/bin/str_replace_editor"),
            "str_replace",
            str(path),
            "--old_str",
            old_str,
            "--new_str",
            new_str,
        ],
        env={**os.environ, "PYTHONPATH": str(TOOLS_DIR / "registry/lib")},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=10,
    )


def test_empty_old_str_on_empty_file_does_not_write(with_tmp_env_file):
    path = with_tmp_env_file.parent / "example.py"
    path.write_bytes(b"")

    result = _str_replace(path, "", "hello")

    assert result.returncode == 22, result.stdout + result.stderr
    assert result.stderr == ""
    assert "ValueError" not in result.stdout
    assert "old_str is empty" in result.stdout
    assert "has been edited" not in result.stdout
    assert path.read_bytes() == b""


def test_empty_old_str_on_nonempty_file_still_rejects_without_writing(with_tmp_env_file):
    path = with_tmp_env_file.parent / "example.py"
    path.write_bytes(b"keep\n")

    result = _str_replace(path, "", "hello")

    assert result.returncode == 16, result.stdout + result.stderr
    assert result.stderr == ""
    assert "Multiple occurrences" in result.stdout
    assert path.read_bytes() == b"keep\n"
