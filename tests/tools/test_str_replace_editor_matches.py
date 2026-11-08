import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
EDITOR = TOOLS / "edit_anthropic" / "bin" / "str_replace_editor"
REGISTRY = TOOLS / "registry" / "lib"


@pytest.mark.parametrize(
    ("contents", "old", "new", "expected", "exit_code", "message"),
    [
        pytest.param(
            "repeat\nrepeat\nrepeat\n", "repeat\nrepeat", "changed", None, 16, "lines [1, 2]", id="overlapping-lines"
        ),
        pytest.param("aaaa\n", "aaa", "changed", None, 16, "lines [1]", id="overlapping-same-line"),
        pytest.param(
            "foo\nbar\nfoo\nbar\n", "foo\nbar", "changed", None, 16, "lines [1, 3]", id="nonoverlapping-lines"
        ),
        pytest.param(
            "foo\nother\nfoo\nother\nfoo\n",
            "foo",
            "changed",
            None,
            16,
            "lines [1, 3, 5]",
            id="legacy-duplicate-locations",
        ),
        pytest.param(
            "before\nonly\none\nafter\n",
            "only\none",
            "changed",
            "before\nchanged\nafter\n",
            0,
            "edited",
            id="unique-multiline",
        ),
        pytest.param(
            "prefix[foo].suffix\n", "[foo].", "changed", "prefixchangedsuffix\n", 0, "edited", id="literal-inline"
        ),
        pytest.param("other\n", "missing", "changed", None, 15, "did not appear verbatim", id="absent"),
        pytest.param("keep\n", "keep", "keep", None, 161, "is the same", id="no-op"),
        pytest.param(
            "no trailing newline", "newline", "ending", "no trailing ending", 0, "edited", id="unterminated-line"
        ),
    ],
)
def test_replace_requires_unique_match(tmp_path, contents, old, new, expected, exit_code, message):
    source = tmp_path / "example.txt"
    source.write_text(contents, encoding="utf-8")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"USE_LINTER": "false", "USE_FILEMAP": "false"}), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(EDITOR), "str_replace", str(source), "--old_str", old, "--new_str", new],
        env={**os.environ, "SWE_AGENT_ENV_FILE": str(registry), "PYTHONPATH": str(REGISTRY)},
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == exit_code, result.stdout + result.stderr
    assert source.read_text(encoding="utf-8") == (contents if expected is None else expected)
    assert message in result.stdout
