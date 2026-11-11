"""If for some reason the .pred file isn't saved, we can extract it from the .traj file."""

import argparse
import json
import re
from pathlib import Path


def run_from_cli(_args: list[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("traj_path", type=Path)
    args = parser.parse_args(_args)
    data = json.loads(args.traj_path.read_text())
    pred_path = args.traj_path.with_suffix(".pred")
    traj_path = args.traj_path.resolve()
    instance_dir = traj_path.parent
    # RetryAgent writes each attempt under an extra attempt_N directory.
    if (
        instance_dir.name != traj_path.stem
        and re.fullmatch(r"attempt_[0-9]+", instance_dir.name)
        and instance_dir.parent.name == traj_path.stem
    ):
        instance_dir = instance_dir.parent

    pred_data = {
        "model_name_or_path": instance_dir.parent.name,
        "model_patch": data["info"]["submission"],
        "instance_id": instance_dir.name,
    }
    pred_path.write_text(json.dumps(pred_data))
