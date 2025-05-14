#!/usr/bin/env python3
import argparse
import collections
import json
from pathlib import Path

import numpy as np

from sweagent.utils.log import get_logger

"""Calculate statistics from .traj files."""

logger = get_logger("quick-stats", emoji="📊")


def quick_stats(directory: Path | str = ".") -> str:
    """Calculate statistics from .traj files.

    Args:
        directory: Directory to search for .traj files (default: current directory)

    Returns:
        str: Summary of statistics
    """
    directory = Path(directory)
    # Find all .traj files
    traj_files = list(directory.glob("**/*.traj"))

    if not traj_files:
        logger.warning("No .traj files found in %s", directory)
        return "No .traj files found."

    # Extract api_calls from each file
    api_calls = []
    files_by_exit_status = collections.defaultdict(list)

    for file_path in traj_files:
        try:
            data = json.loads(file_path.read_text())
            # Extract the api_calls value using dictionary path
            if "info" in data and "model_stats" in data["info"] and "api_calls" in data["info"]["model_stats"]:
                api_calls.append(data["info"]["model_stats"]["api_calls"])
            if "info" in data and "exit_status" in data["info"]:
                status = data["info"]["exit_status"]
                files_by_exit_status[status].append(file_path)
        except Exception as e:
            logger.error("Error processing %s: %s", file_path, e)

    files_by_exit_status = dict(sorted(files_by_exit_status.items(), key=lambda x: len(x[1]), reverse=True))

    if not api_calls:
        logger.warning("No valid api_calls data found in the .traj files")
        return "No valid api_calls data found in the .traj files."

    # Calculate and return the average
    logger.info("Exit statuses:")
    # Sort exit statuses by count (highest to lowest)
    for status, files in files_by_exit_status.items():
        logger.info("%s: %d", status, len(files))

    average_api_calls = np.mean(api_calls)
    logger.info("Avg api calls: %s", average_api_calls)

    # Print exit statuses in the requested format
    result = []
    for status, files in files_by_exit_status.items():
        result.append(f"\n## `{status}`\n")
        # Extract unique subdirectories instead of full paths
        subdirs = {str(Path(file_path).parent) for file_path in files}
        result.append(" ".join(subdirs))

    return "\n".join(result)


def get_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory",
        type=Path,
        nargs="?",
        default=Path("."),
        help="Directory to search for .traj files (default: current directory)",
    )
    return parser


def run_from_cli(args: list[str] | None = None) -> None:
    cli_parser = get_cli_parser()
    cli_args = cli_parser.parse_args(args)

    result = quick_stats(cli_args.directory)
    print(result)


if __name__ == "__main__":
    run_from_cli()
