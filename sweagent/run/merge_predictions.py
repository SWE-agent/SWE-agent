import argparse
import errno
import json
import os
import stat
from pathlib import Path
from tempfile import TemporaryDirectory

from sweagent.utils.log import get_logger

"""Merge multiple predictions into a single file."""


logger = get_logger("merge", emoji="➕")


def merge_predictions(directories: list[Path], output: Path | None = None) -> None:
    """Merge predictions found in `directories` into a single JSON file.

    Args:
        directory: Directory containing predictions.
        output: Output file. If not provided, the merged predictions will be
            written to `directory/preds.json`.
    """
    preds = []
    for directory in directories:
        new = list(directory.rglob("*.pred"))
        preds.extend(new)
        logger.debug("Found %d predictions in %s", len(new), directory)
    logger.info("Found %d predictions", len(preds))
    if not preds:
        logger.warning("No predictions found in %s", directory)
        return
    if output is None:
        output = directories[0] / "preds.json"
    data = {}
    for pred in preds:
        _data = json.loads(pred.read_text())
        instance_id = _data["instance_id"]
        if "model_patch" not in _data:
            logger.warning("Prediction %s does not contain a model patch. SKIPPING", pred)
            continue
        # Ensure model_patch is a string
        _data["model_patch"] = str(_data["model_patch"]) if _data["model_patch"] is not None else ""
        if instance_id in data:
            msg = f"Duplicate instance ID found: {instance_id}"
            raise ValueError(msg)
        data[instance_id] = _data
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_aggregate(output, json.dumps(data, indent=4))
    logger.info("Wrote merged predictions to %s", output)


def _write_aggregate(path: Path, text: str) -> None:
    """Replace an ordinary aggregate only after the new contents are complete."""
    target = path.resolve()
    try:
        previous = target.stat()
    except FileNotFoundError:
        previous = None

    if previous is not None:
        if not stat.S_ISREG(previous.st_mode) or previous.st_nlink > 1 or not hasattr(os, "listxattr"):
            # Keep shared inodes, special destinations and uninspectable ACLs intact.
            target.write_text(text)
            return
        # A rename alone would skip write permissions on the original file.
        os.close(os.open(target, os.O_WRONLY))

    try:
        staging = TemporaryDirectory(dir=target.parent)
    except PermissionError:
        if previous is None:
            raise
        # A writable existing file can still be updated when its parent denies staging.
        target.write_text(text)
        return

    with staging as directory:
        staged = Path(directory) / "predictions"
        staged.write_text(text)
        if previous is not None:
            try:
                _copy_output_access(target, staged, previous)
            except PermissionError:
                # Writing an existing file doesn't require permission to copy its metadata.
                target.write_text(text)
                return
        staged.replace(target)


def _copy_output_access(target: Path, staged: Path, previous: os.stat_result) -> None:
    staged_stat = staged.stat()
    if (staged_stat.st_uid, staged_stat.st_gid) != (previous.st_uid, previous.st_gid):
        os.chown(staged, previous.st_uid, previous.st_gid)

    mode = stat.S_IMODE(previous.st_mode)
    staged.chmod(mode)

    expected_attrs = _output_attributes(target)
    staged_attrs = _output_attributes(staged)
    for name in staged_attrs.keys() - expected_attrs.keys():
        os.removexattr(staged, name)
    for name, value in expected_attrs.items():
        if staged_attrs.get(name) != value:
            os.setxattr(staged, name, value)

    actual = staged.stat()
    if (
        (actual.st_uid, actual.st_gid) != (previous.st_uid, previous.st_gid)
        or stat.S_IMODE(actual.st_mode) != mode
        or _output_attributes(staged) != expected_attrs
    ):
        raise OSError(errno.EIO, "Cannot preserve the aggregate's access metadata", target)


def _output_attributes(path: Path) -> dict[str, bytes]:
    try:
        names = os.listxattr(path)
    except OSError as error:
        if error.errno != errno.ENOTSUP:
            raise
        return {}
    return {name: os.getxattr(path, name) for name in names}


def get_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directories", type=Path, help="Directory containing predictions", nargs="+")
    parser.add_argument("--output", type=Path, help="Output file")
    return parser


def run_from_cli(args: list[str] | None = None) -> None:
    cli_parser = get_cli_parser()
    cli_args = cli_parser.parse_args(args)
    merge_predictions(cli_args.directories, cli_args.output)


if __name__ == "__main__":
    run_from_cli()
