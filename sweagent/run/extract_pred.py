"""If for some reason the .pred file isn't saved, we can extract it from the .traj file."""

import argparse
import json
import re
from pathlib import Path


def _matches_aggregate_attempt(aggregate_path: Path, index: int, trajectory: dict) -> bool:
    try:
        if not aggregate_path.is_file():
            return False
        aggregate = json.loads(aggregate_path.read_text())
    except (OSError, ValueError, RecursionError):
        return False

    attempts = aggregate.get("attempts") if isinstance(aggregate, dict) else None
    return isinstance(attempts, list) and index < len(attempts) and attempts[index] == trajectory


def run_from_cli(_args: list[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("traj_path", type=Path)
    args = parser.parse_args(_args)
    data = json.loads(args.traj_path.read_text())
    pred_path = args.traj_path.with_suffix(".pred")
    traj_path = args.traj_path.resolve()
    instance_dir = traj_path.parent
    # RetryAgent writes each attempt under an extra attempt_N directory.
    attempt = re.fullmatch(r"attempt_([0-9]+)", instance_dir.name)
    if attempt and instance_dir.parent.name == traj_path.stem:
        # When the attempt directory also matches the instance ID, require
        # corroboration from the aggregate to distinguish the two layouts.
        if instance_dir.name != traj_path.stem or _matches_aggregate_attempt(
            instance_dir.parent / traj_path.name, int(attempt[1]), data
        ):
            instance_dir = instance_dir.parent

    pred_data = {
        "model_name_or_path": instance_dir.parent.name,
        "model_patch": data["info"]["submission"],
        "instance_id": instance_dir.name,
    }
    pred_path.write_text(json.dumps(pred_data))
