import argparse
import json
from pathlib import Path

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
        logger.warning("No predictions found in %s", directories)
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
    output.write_text(json.dumps(data, indent=4))
    logger.info("Wrote merged predictions to %s", output)


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
