"""Regression test: bundle config.yaml must be read as UTF-8 regardless of locale."""

import json
import os
import subprocess
import sys
from pathlib import Path

DESCRIPTION = "修复问题 café \U0001f680"


def test_bundle_config_reads_utf8_with_legacy_locale(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        f'tools:\n  fix:\n    signature: "fix"\n    docstring: "{DESCRIPTION}"\n    arguments: []\n',
        encoding="utf-8",
    )
    script = "\n".join(
        [
            "import json, sys",
            "from pathlib import Path",
            "from sweagent.tools.bundle import Bundle",
            "bundle = Bundle(path=Path(sys.argv[1]))",
            "print(json.dumps(bundle.commands[0].docstring))",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-X", "utf8=0", "-c", script, str(tmp_path)],
        env={**os.environ, "LC_ALL": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout.splitlines()[-1]) == DESCRIPTION
