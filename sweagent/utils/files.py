import json
import os
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import yaml


def write_checkpoint(path: Path, text: str) -> None:
    """Replace an ordinary checkpoint only after its complete contents are written."""
    target = path.resolve()
    try:
        previous = target.stat()
    except FileNotFoundError:
        previous = None

    if previous is not None:
        if not stat.S_ISREG(previous.st_mode) or previous.st_nlink > 1:
            # Explicitly shared inodes and special files depend on in-place writes.
            target.write_text(text)
            return
        # Replacement alone would bypass write permissions on the original file.
        os.close(os.open(target, os.O_WRONLY))

    with TemporaryDirectory(dir=target.parent, ignore_cleanup_errors=True) as directory:
        staged = Path(directory) / "checkpoint"
        staged.write_text(text)
        if previous is not None:
            staged.chmod(stat.S_IMODE(previous.st_mode))
        staged.replace(target)


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
    if path.suffix == ".yaml":
        return yaml.safe_load(path.read_text())
    msg = f"Unsupported file extension: {path.suffix}"
    raise NotImplementedError(msg)
