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
        return json.loads(path.read_text())
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if path.suffix in [".yaml", ".yml"]:
        return yaml.safe_load(path.read_text())
    msg = f"Unsupported file extension: {path.suffix}"
    raise NotImplementedError(msg)
