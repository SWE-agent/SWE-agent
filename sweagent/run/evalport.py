"""Export a SWE-agent ``results.json`` as an EvalPort ResultSet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def to_evalport(results: dict[str, Any], run_id: str, *, started_at: str | None = None) -> dict[str, Any]:
    """Convert SWE-bench run results to the EvalPort ResultSet shape.

    ``passed`` counts submitted instances that resolved, so the summary matches
    the result rows.
    """
    submitted = set(results["submitted_ids"])
    resolved = set(results.get("resolved_ids", results.get("resolved", [])))
    passed_ids = submitted & resolved
    payload: dict[str, Any] = {
        "version": "1.0.0",
        "suite_id": "swe-bench",
        "run_id": run_id,
        "results": [
            {
                "test_case_id": instance_id,
                "passed": instance_id in passed_ids,
                "grader_results": [
                    {
                        "grader_id": "resolved",
                        "type": "custom",
                        "score": 1.0 if instance_id in passed_ids else 0.0,
                        "passed": instance_id in passed_ids,
                    }
                ],
            }
            for instance_id in sorted(submitted)
        ],
        "summary": {
            "total": len(submitted),
            "passed": len(passed_ids),
            "pass_rate": (len(passed_ids) / len(submitted)) if submitted else 0,
        },
    }
    if started_at is not None:
        payload["started_at"] = started_at
    return payload


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write an EvalPort ResultSet from results.json")
    parser.add_argument("results", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--started-at")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    payload = to_evalport(json.loads(args.results.read_text()), args.run_id, started_at=args.started_at)
    text = json.dumps(payload, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
