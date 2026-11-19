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
    ("contents", "args", "expected"),
    [
        pytest.param(
            "def\t f():\n    return 1\n\nx = 1\n",
            ["str_replace", "--old_str", "return 1", "--new_str", "return 2"],
            "def\t f():\n    return 2\n\nx = 1\n",
            id="str-replace-keeps-tab-on-untouched-line",
        ),
        pytest.param(
            "a\tb\n\tprint(1)\nc\td\n",
            ["str_replace", "--old_str", "        print(1)", "--new_str", "        print(2)"],
            "a\tb\n        print(2)\nc\td\n",
            id="str-replace-matches-tab-expanded-old-str",
        ),
        pytest.param(
            "import os\n\tprint(os.getcwd())\n",
            ["insert", "--insert_line", "1", "--new_str", "# inserted"],
            "import os\n# inserted\n\tprint(os.getcwd())\n",
            id="insert-keeps-tab-on-untouched-line",
        ),
        pytest.param(
            "all:\n\techo hi\n",
            ["insert", "--insert_line", "2", "--new_str", "\techo there"],
            "all:\n\techo hi\n\techo there\n",
            id="insert-writes-tab-from-new-str",
        ),
    ],
)
def test_edit_does_not_expand_tabs_outside_the_edited_text(tmp_path, contents, args, expected):
    source = tmp_path / "example.txt"
    source.write_text(contents, encoding="utf-8")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"USE_LINTER": "false", "USE_FILEMAP": "false"}), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(EDITOR), args[0], str(source), *args[1:]],
        env={**os.environ, "SWE_AGENT_ENV_FILE": str(registry), "PYTHONPATH": str(REGISTRY)},
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert source.read_text(encoding="utf-8") == expected
