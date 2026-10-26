import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("problem_id", [None, "explicit-id"])
@pytest.mark.parametrize("text", ["Fix this bug", "Fix the calf\u00e9: \u4fee\u590d\u95ee\u9898 \U0001f680"])
def test_file_problem_statement_reads_utf8_with_legacy_locale(
    tmp_path: Path, problem_id: str | None, text: str
) -> None:
    path = tmp_path / "problem.md"
    path.write_text(text, encoding="utf-8")
    script = "\n".join(
        [
            "import json, sys",
            "from pathlib import Path",
            "from sweagent.agent.problem_statement import FileProblemStatement",
            "kwargs = {'id': json.loads(sys.argv[2])} if sys.argv[2] != 'null' else {}",
            "problem = FileProblemStatement(path=Path(sys.argv[1]), **kwargs)",
            "print(json.dumps([problem.get_problem_statement(), problem.id]))",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-X", "utf8=0", "-c", script, str(path), json.dumps(problem_id)],
        env={**os.environ, "LC_ALL": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    expected_id = problem_id if problem_id is not None else hashlib.sha256(text.encode("utf-8")).hexdigest()[:6]
    assert json.loads(completed.stdout.splitlines()[-1]) == [text, expected_id]
