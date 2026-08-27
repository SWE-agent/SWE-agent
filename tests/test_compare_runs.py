import json
from pathlib import Path

import pytest

from sweagent.run.compare_runs import run_from_cli


def test_compare_many_handles_run_without_common_instances(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    results = [
        {"submitted_ids": ["case-a"], "resolved_ids": ["case-a"]},
        {"submitted_ids": ["case-b"], "resolved_ids": ["case-b"]},
        {"submitted_ids": ["case-a"], "resolved_ids": []},
    ]
    paths = []
    for index, result in enumerate(results):
        run_dir = tmp_path / f"run-{index}"
        run_dir.mkdir()
        (run_dir / "results.json").write_text(json.dumps(result))
        paths.append(str(run_dir))

    run_from_cli(paths)

    rows = [line.split() for line in capsys.readouterr().out.splitlines() if "run-" in line]
    assert rows == [
        ["0", "run-0", "1", "1.00"],
        ["1", "run-1", "0", "N/A"],
        ["2", "run-2", "0", "0.00"],
    ]
