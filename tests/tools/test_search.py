import shutil
import subprocess
from pathlib import Path

import pytest

from sweagent import TOOLS_DIR

SEARCH_DIR_SCRIPT = TOOLS_DIR / "search" / "bin" / "search_dir"


def find_bash() -> str | None:
    for candidate in [shutil.which("bash"), "C:/Program Files/Git/bin/bash.exe", "/bin/bash", "/usr/bin/bash"]:
        if not candidate:
            continue
        try:
            res = subprocess.run([candidate, "-c", "echo ok"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and "ok" in res.stdout:
                return candidate
        except Exception:
            continue
    return None


BASH = find_bash()


@pytest.mark.skipif(BASH is None, reason="bash required to test search_dir")
def test_search_dir_spaces_and_matches(tmp_path: Path):
    sub = tmp_path / "sub folder"
    sub.mkdir()
    (sub / "sample_one.txt").write_text("target 1\ntarget 2\n")
    (tmp_path / "sample_two.txt").write_text("target 3\n")
    (tmp_path / "sample_three.txt").write_text("other\n")

    res = subprocess.run(
        [BASH, str(SEARCH_DIR_SCRIPT.as_posix()), "target", str(tmp_path.as_posix())],
        capture_output=True,
        text=True,
        check=True,
    )
    output = res.stdout
    assert 'Found 3 matches for "target" in ' in output
    assert "sample_two.txt (1 matches)" in output
    assert "sub folder/sample_one.txt (2 matches)" in output
    assert "sample_three.txt" not in output


@pytest.mark.skipif(BASH is None, reason="bash required to test search_dir")
def test_search_dir_colon_filenames():
    script = (
        "set -e\n"
        "tmp=$(mktemp -d)\n"
        'printf "needle 1\\nneedle 2\\n" > "$tmp/sample:one.txt"\n'
        'printf "needle 3\\n" > "$tmp/sample:two.txt"\n'
        f'"{BASH}" "{SEARCH_DIR_SCRIPT.as_posix()}" needle "$tmp"\n'
        'rm -rf "$tmp"\n'
    )
    res = subprocess.run([BASH, "-c", script], capture_output=True, text=True, check=True)
    output = res.stdout
    assert 'Found 3 matches for "needle" in ' in output
    assert "sample:one.txt (2 matches)" in output
    assert "sample:two.txt (1 matches)" in output
