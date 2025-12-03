"""Remove unfinished trajectories."""

import argparse
import shutil
from pathlib import Path

from sweagent.utils.files import load_file
from sweagent.utils.log import get_logger

logger = get_logger("remove_unfinished")


def remove_unfinished(base_dir: Path, dry_run: bool = True) -> None:
    """Remove unfinished trajectories."""
    to_remove = []
    for directory in base_dir.iterdir():
        if not directory.is_dir():
            continue
        if "__" not in directory.name:
            continue
        trajs = list(directory.glob("*.traj"))
        if not trajs:
            logger.info("No trajectories found in %s", directory)
            continue
        if len(trajs) > 1:
            logger.warning("Found multiple trajectories in %s. Skipping.", directory)
            continue
        try:
            traj = load_file(trajs[0])
        except Exception as e:
            logger.warning("Error loading trajectory %s: %s. Adding to remove list.", trajs[0], e)
            to_remove.append(directory)
            continue
        submission = traj.get("info", {}).get("submission", None)
        if submission is None:
            logger.warning("No submission found in %s. Adding to remove list.", directory)
            to_remove.append(directory)
            continue
    if dry_run:
        logger.info("Would remove %d unfinished trajectories.", len(to_remove))
        for directory in to_remove:
            logger.info(directory)
    else:
        for directory in to_remove:
            logger.info("Removing %s", directory)
            shutil.rmtree(directory)


def get_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base_dir", type=Path, help="Base directory", default=Path("."))
    parser.add_argument("--remove", action="store_true", help="Remove unfinished trajectories")
    return parser


def run_from_cli(args: list[str] | None = None) -> None:
    cli_parser = get_cli_parser()
    cli_args = cli_parser.parse_args(args)
    remove_unfinished(cli_args.base_dir, dry_run=not cli_args.remove)


if __name__ == "__main__":
    run_from_cli()
