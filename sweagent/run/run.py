"""[cyan][bold]Main command line interface for SWE-agent.[/bold][/cyan]

[cyan][bold]=== USAGE ===[/bold][/cyan]

[green]sweagent <command> [options][/green]

Display usage instructions for a specific command:

[green]sweagent <command> [bold]--help[/bold][/green]

[cyan][bold]=== SUBCOMMANDS TO RUN SWE-AGENT ===[/bold][/cyan]

[bold][green]run[/green][/bold]: Run swe-agent on a single problem statement, for example a github issue.
[bold][green]run-batch[/green][/bold]: Run swe-agent on a batch of problem statements, e.g., on SWE-Bench.

[cyan][bold]=== MISC SUBCOMMANDS ===[/bold][/cyan]

[bold][green]merge-preds[/green][/bold]: Merge multiple prediction files into a single file. In most cases
    [green]run-batch[/green] will already do this, but you can use this to merge predictions
    from multiple directories.
[bold][green]inspect[/green][/bold]: Open a single trajectory file in a terminal-based viewer.
[bold][green]inspector[/green][/bold]: Open trajectories in a web-based viewer.
[bold][green]run-replay[/green][/bold]: Replay a trajectory file or a demo file.
    This can be useful to fill in environment output when creating demonstrations.
[bold][green]traj-to-demo[/green][/bold]: Convert a trajectory file to an easy to edit demo file.
[bold][green]run-api[/green][/bold]: Run swe-agent as a backend for a GUI
"""

import argparse
import sys

import rich


def get_cli():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "command",
        choices=["run", "run-batch", "run-replay", "traj-to-demo", "run-api", "merge-preds", "inspect", "inspector"],
        nargs="?",
    )
    parser.add_argument("-h", "--help", action="store_true", help="Show this help message and exit")
    return parser


def main(args: list[str] | None = None):
    if args is None:
        args = sys.argv[1:]
    cli = get_cli()
    parsed_args, remaining_args = cli.parse_known_args(args)  # type: ignore
    command = parsed_args.command
    show_help = parsed_args.help
    if show_help:
        if not command:
            # Show main help
            rich.print(__doc__)
            sys.exit(0)
        else:
            # Add to remaining_args
            remaining_args.append("--help")
    elif not command:
        cli.print_help()
        sys.exit(2)
    # Defer imports to avoid unnecessary long loading times
    if command == "run":
        from sweagent.run.run_single import run_from_cli as run_single_main

        run_single_main(remaining_args)
    elif command == "run-batch":
        from sweagent.run.run_batch import run_from_cli as run_batch_main

        run_batch_main(remaining_args)
    elif command == "run-replay":
        from sweagent.run.run_replay import run_from_cli as run_replay_main

        run_replay_main(remaining_args)
    elif command == "traj-to-demo":
        from sweagent.run.run_traj_to_demo import run_from_cli as convert_traj_to_demo_main

        convert_traj_to_demo_main(remaining_args)
    elif command == "run-api":
        from sweagent.api.server import run_from_cli as run_api_main

        run_api_main(remaining_args)
    elif command == "merge-preds":
        from sweagent.run.merge_predictions import run_from_cli as merge_predictions_main

        merge_predictions_main(remaining_args)
    elif command == "inspector":
        from sweagent.inspector.server import run_from_cli as inspector_main

        inspector_main(remaining_args)
    elif command == "inspect":
        from sweagent.run.inspector_cli import main as inspect_main

        inspect_main(remaining_args)
    else:
        msg = f"Unknown command: {command}"
        raise ValueError(msg)


if __name__ == "__main__":
    main()