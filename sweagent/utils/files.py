import json
from pathlib import Path
from typing import Any

import yaml


def load_file(path: Path | str | None) -> Any:
    """Load files based on their extension."""
    if path is None:
        return None
    if isinstance(path, str):
        path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_dir():
        from datasets import load_from_disk

        return load_from_disk(path)
    if path.suffix in [".json", ".traj"]:
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if path.suffix == ".yaml":
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    msg = f"Unsupported file extension: {path.suffix}"
    raise NotImplementedError(msg)
