import os
import subprocess
import sys
from pathlib import Path

from sweagent import TOOLS_DIR


def _run(path: Path, *args: str):
    return subprocess.run(
        [sys.executable, str(TOOLS_DIR / "edit_anthropic/bin/str_replace_editor"), *args, str(path)],
        env={**os.environ, "PYTHONPATH": str(TOOLS_DIR / "registry/lib")},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=10,
    )


def test_str_replace_keeps_crlf(with_tmp_env_file):
    path = with_tmp_env_file.parent / "example.py"
    path.write_bytes(b"one\r\ntwo\r\n")

    result = _run(path, "str_replace", "--old_str", "one", "--new_str", "1")

    assert result.returncode == 0, result.stdout + result.stderr
    assert path.read_bytes() == b"1\r\ntwo\r\n"


def test_insert_keeps_crlf(with_tmp_env_file):
    path = with_tmp_env_file.parent / "example.py"
    path.write_bytes(b"one\r\ntwo\r\n")

    result = _run(path, "insert", "--insert_line", "1", "--new_str", "mid")

    assert result.returncode == 0, result.stdout + result.stderr
    assert path.read_bytes() == b"one\r\nmid\r\ntwo\r\n"


def test_str_replace_keeps_cr_and_lf(with_tmp_env_file):
    path = with_tmp_env_file.parent / "example.py"
    path.write_bytes(b"one\rtwo\r")
    result = _run(path, "str_replace", "--old_str", "one", "--new_str", "1")
    assert result.returncode == 0, result.stdout + result.stderr
    assert path.read_bytes() == b"1\rtwo\r"

    path.write_bytes(b"one\ntwo\n")
    result = _run(path, "str_replace", "--old_str", "two", "--new_str", "2")
    assert result.returncode == 0, result.stdout + result.stderr
    assert path.read_bytes() == b"one\n2\n"
