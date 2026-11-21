"""Regression test: the static trajectory viewer must use UTF-8 regardless of locale."""

import json
import os
import subprocess
import sys
from pathlib import Path

GOLD_PATCH = "修复问题 café \U0001f680"
INSTANCE_ID = "my-instance"


def test_save_static_viewer_reads_dataset_as_utf8_with_legacy_locale(tmp_path: Path) -> None:
    traj_dir = tmp_path / "run" / INSTANCE_ID
    traj_dir.mkdir(parents=True)
    traj = traj_dir / f"{INSTANCE_ID}.traj"
    traj.write_text(
        json.dumps(
            {
                "info": {"exit_status": "submitted", "submission": "diff --git a/file b/file\n"},
                "trajectory": [],
                "history": [{"role": "user", "content": "Please fix the bug."}],
            }
        ),
        encoding="utf-8",
    )
    dataset = tmp_path / "dataset.json"
    dataset.write_text(
        json.dumps([{"instance_id": INSTANCE_ID, "patch": GOLD_PATCH, "test_patch": ""}], ensure_ascii=False),
        encoding="utf-8",
    )
    # The static viewer looks for args.yaml next to the trajectory; absolute
    # data_path values are kept as-is by its package-relative resolution.
    (traj_dir / "args.yaml").write_text(
        f"environment:\n  data_path: {dataset.as_posix()}\n",
        encoding="utf-8",
    )

    script = "\n".join(
        [
            "import sys",
            "from pathlib import Path",
            "from sweagent.inspector.static import save_static_viewer",
            "save_static_viewer(Path(sys.argv[1]))",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-X", "utf8=0", "-c", script, str(traj)],
        env={
            **os.environ,
            "LC_ALL": "C",
            "PYTHONCOERCECLOCALE": "0",
            "PYTHONIOENCODING": "utf-8",
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    html = traj.with_suffix(".html").read_text(encoding="utf-8")
    assert "Please fix the bug." in html
