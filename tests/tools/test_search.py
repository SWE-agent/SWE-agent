import subprocess
from pathlib import Path

import pytest

from sweagent import TOOLS_DIR


@pytest.mark.parametrize(
    ("matching_lines", "hits_per_line"),
    [(0, 1), (100, 1), (101, 1), (500, 1), (1, 101)],
)
def test_search_file_match_limit(tmp_path: Path, matching_lines: int, hits_per_line: int):
    file = (tmp_path / "test.txt").resolve()
    content = " ".join(["needle"] * hits_per_line)
    file.write_text((content + "\n") * matching_lines + "unrelated line\n")

    result = subprocess.run(
        ["bash", str(TOOLS_DIR / "search" / "bin" / "search_file"), "needle", str(file)],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )

    assert not result.stderr
    if matching_lines == 0:
        expected = [f'No matches found for "needle" in {file}']
    elif matching_lines > 100:
        expected = [f'More than {matching_lines} lines matched for "needle" in {file}. Please narrow your search.']
    else:
        expected = [
            f'Found {matching_lines} matches for "needle" in {file}:',
            *(f"Line {i}:{content}" for i in range(1, matching_lines + 1)),
            f'End of matches for "needle" in {file}',
        ]
    assert result.stdout.splitlines() == expected
