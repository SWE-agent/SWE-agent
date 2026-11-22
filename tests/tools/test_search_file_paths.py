import subprocess
from pathlib import Path

import pytest

from sweagent import TOOLS_DIR


@pytest.mark.parametrize("relative_path", ["plain.txt", "sample:one.txt", "dir:part/file name.txt", "sample:1"])
def test_search_file_preserves_matching_lines(tmp_path: Path, relative_path: str):
    file = (tmp_path / relative_path).resolve()
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("not a match\nneedle: first\\value\nother\n  needle: second")

    result = subprocess.run(
        ["bash", str(TOOLS_DIR / "search" / "bin" / "search_file"), "needle", str(file)],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )

    assert result.stderr == ""
    assert result.stdout.splitlines() == [
        f'Found 2 matches for "needle" in {file}:',
        "Line 2:needle: first\\value",
        "Line 4:  needle: second",
        f'End of matches for "needle" in {file}',
    ]
