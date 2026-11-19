import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

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


@pytest.mark.parametrize("max_expansion", [0, 8])
@pytest.mark.parametrize(
    "separator",
    ["\f", "\v", "\x1c", "\x1d", "\x1e", "\x85", "\N{LINE SEPARATOR}", "\N{PARAGRAPH SEPARATOR}"],
    ids=["form-feed", "vertical-tab", "file-separator", "group-separator", "record-separator", "nel", "ls", "ps"],
)
def test_str_replace_confirms_edits_with_non_lf_separators(with_tmp_env_file, separator, max_expansion):
    with_tmp_env_file.write_text(
        json.dumps({"MAX_WINDOW_EXPANSION_EDIT_CONFIRM": str(max_expansion)}), encoding="utf-8"
    )
    path = with_tmp_env_file.parent / "example.py"
    original = f"def f():\n {separator}  return 1\n\nx"
    path.write_text(original, encoding="utf-8")

    result = _str_replace(path, "1", "x = 1")

    assert path.read_bytes() == original.replace("1", "x = 1").encode("utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ""
    assert f"The file {path} has been edited." in result.stdout
    assert f"     2\t {separator}  return x = 1\n" in result.stdout
    assert "     4\tx\n" in result.stdout
    assert "Review the changes" in result.stdout


@pytest.mark.parametrize("max_expansion", [0, 8])
def test_str_replace_confirms_deleting_entire_file(with_tmp_env_file, max_expansion):
    with_tmp_env_file.write_text(
        json.dumps({"MAX_WINDOW_EXPANSION_EDIT_CONFIRM": str(max_expansion)}), encoding="utf-8"
    )
    path = with_tmp_env_file.parent / "example.py"
    path.write_text("ca", encoding="utf-8")

    result = _str_replace(path, "ca", "")

    assert path.read_bytes() == b""
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ""
    assert f"The file {path} has been edited." in result.stdout
    assert "     1\t\nReview the changes" in result.stdout


def test_str_replace_confirms_lf_edit_near_end_of_file(with_tmp_env_file):
    path = with_tmp_env_file.parent / "example.py"
    original = "# unchanged\n" * 10 + "return 1\n"
    path.write_text(original, encoding="utf-8")

    result = _str_replace(path, "return 1", "return 2\n# added")

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ""
    assert path.read_bytes() == original.replace("return 1", "return 2\n# added").encode("utf-8")
    assert "    11\treturn 2\n    12\t# added\n" in result.stdout
    assert "Review the changes" in result.stdout


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
@pytest.mark.parametrize(
    ("old_str", "new_str", "exit_code"),
    [("absent", "replacement", 15), ("same", "replacement", 16), ("unique", "unique", 161)],
    ids=["missing", "ambiguous", "unchanged"],
)
def test_str_replace_rejected_edits_leave_file_unchanged(with_tmp_env_file, newline, old_str, new_str, exit_code):
    path = with_tmp_env_file.parent / "example.py"
    original = newline.join(["same", "same", "unique", ""]).encode("utf-8")
    path.write_bytes(original)

    result = _str_replace(path, old_str, new_str)

    assert result.returncode == exit_code, result.stdout + result.stderr
    assert result.stderr == ""
    assert "No replacement was performed" in result.stdout
    assert "has been edited" not in result.stdout
    assert path.read_bytes() == original
