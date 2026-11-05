from __future__ import annotations

import json

from sweagent.run.evalport import main, to_evalport


def test_to_evalport_marks_resolved_submissions():
    payload = to_evalport(
        {"submitted_ids": ["b", "a", "c"], "resolved_ids": ["a", "missing"]},
        "run-1",
        started_at="2026-11-05T00:00:00Z",
    )
    assert payload["version"] == "1.0.0"
    assert payload["suite_id"] == "swe-bench"
    assert payload["run_id"] == "run-1"
    assert payload["started_at"] == "2026-11-05T00:00:00Z"
    assert [row["test_case_id"] for row in payload["results"]] == ["a", "b", "c"]
    assert [row["passed"] for row in payload["results"]] == [True, False, False]
    assert payload["summary"] == {"total": 3, "passed": 1, "pass_rate": 1 / 3}


def test_to_evalport_accepts_the_resolved_alias():
    payload = to_evalport({"submitted_ids": ["a"], "resolved": ["a"]}, "run-2")
    assert payload["results"][0]["passed"] is True
    assert "started_at" not in payload


def test_evalport_cli_writes_json(tmp_path, capsys):
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"submitted_ids": ["a"], "resolved_ids": []}))
    main([str(path), "--run-id", "cli"])
    written = json.loads(capsys.readouterr().out)
    assert written["run_id"] == "cli"
    assert written["summary"]["passed"] == 0
