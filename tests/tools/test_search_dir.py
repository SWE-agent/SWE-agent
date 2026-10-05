import subprocess
from pathlib import Path

import pytest

from sweagent import TOOLS_DIR


@pytest.mark.parametrize("filename", ["plain.txt", "two words.txt", "two\twords.txt"])
def test_search_dir_preserves_complete_matching_paths(tmp_path: Path, filename: str):
    directory = tmp_path / "source tree"
    directory.mkdir()
    file = directory / filename
    file.write_text("needle\nunrelated\nneedle again\n")
    (directory / "unmatched.txt").write_text("unrelated\n")

    result = subprocess.run(
        ["bash", str(TOOLS_DIR / "search" / "bin" / "search_dir"), "needle", str(directory)],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )

    assert not result.stderr
    assert result.stdout.splitlines() == [
        f'Found 2 matches for "needle" in {directory}:',
        f"{file} (2 matches)",
        f'End of matches for "needle" in {directory}',
    ]
