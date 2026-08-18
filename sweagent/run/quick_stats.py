#!/usr/bin/env python3
import argparse
import collections
import json
from pathlib import Path
from typing import Any

import numpy as np

from sweagent.utils.log import get_logger

"""Calculate statistics from .traj files."""

logger = get_logger("quick-stats", emoji="📊")


def _collect_stats(directory: Path | str = ".") -> tuple[dict[str, Any], dict[str, list[Path]]]:
    directory = Path(directory)
    traj_files = list(directory.glob("**/*.traj"))
    api_calls = []
    invalid_trajectory_count = 0
    files_by_exit_status = collections.defaultdict(list)

    for file_path in traj_files:
        try:
            data = json.loads(file_path.read_text())
            if "info" in data and "model_stats" in data["info"] and "api_calls" in data["info"]["model_stats"]:
                api_calls.append(data["info"]["model_stats"]["api_calls"])
            if "info" in data and "exit_status" in data["info"]:
                files_by_exit_status[data["info"]["exit_status"]].append(file_path)
        except Exception as e:
            invalid_trajectory_count += 1
            logger.error("Error processing %s: %s", file_path, e)

    files_by_exit_status = dict(sorted(files_by_exit_status.items(), key=lambda item: (-len(item[1]), str(item[0]))))
    summary = {
        "trajectory_count": len(traj_files),
        "valid_trajectory_count": len(traj_files) - invalid_trajectory_count,
        "invalid_trajectory_count": invalid_trajectory_count,
        "average_api_calls": float(np.mean(api_calls)) if api_calls else None,
        "exit_status_counts": {str(status): len(files) for status, files in sorted(files_by_exit_status.items())},
    }
    return summary, files_by_exit_status


def collect_stats(directory: Path | str = ".") -> dict[str, Any]:
    """Return a machine-readable summary of trajectory statistics."""
    summary, _ = _collect_stats(directory)
    return summary


def quick_stats(directory: Path | str = ".") -> str:
    """Calculate statistics from .traj files.

    Args:
        directory: Directory to search for .traj files (default: current directory)

    Returns:
        str: Summary of statistics
    """
    directory = Path(directory)
    summary, files_by_exit_status = _collect_stats(directory)

    if summary["trajectory_count"] == 0:
        logger.warning("No .traj files found in %s", directory)
        return "No .traj files found."

    if summary["average_api_calls"] is None:
        logger.warning("No valid api_calls data found in the .traj files")
        return "No valid api_calls data found in the .traj files."

    # Calculate and return the average
    logger.info("Exit statuses:")
    # Sort exit statuses by count (highest to lowest)
    for status, files in files_by_exit_status.items():
        logger.info("%s: %d", status, len(files))

    logger.info("Avg api calls: %s", summary["average_api_calls"])

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
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    return parser


def run_from_cli(args: list[str] | None = None) -> None:
    cli_parser = get_cli_parser()
    cli_args = cli_parser.parse_args(args)

    if cli_args.format == "json":
        print(json.dumps(collect_stats(cli_args.directory), sort_keys=True))
    else:
        print(quick_stats(cli_args.directory))


if __name__ == "__main__":
    run_from_cli()
