"""Convert a trajectory file to a yaml file for editing of demos.
You can then load the yaml file with `run_replay.py` to replay the actions in an environment to get
environment output.
"""

from __future__ import annotations

import json
from argparse import ArgumentParser
from pathlib import Path

from sweagent.utils.log import get_logger
from sweagent.utils.serialization import _yaml_serialization_with_linebreaks

logger = get_logger("traj2demo")

DEMO_COMMENT = """# This is a demo file generated from trajectory file:
# {traj_path}
# You can use this demo file to replay the actions in the trajectory with run_replay.py.
# You can edit the content of the actions in this file to modify the replay behavior.
# NOTICE:
#         Only the actions of the assistant will be replayed.
#         You do not need to modify the observation's contents or any other fields.
#         You can add or remove actions to modify the replay behavior."""


def save_demo(data: str | dict | list, file: Path, traj_path: Path) -> None:
    """Save demo data as a yaml file. Takes care of multi-line strings and adds a header."""
    content = _yaml_serialization_with_linebreaks(data)
    header = DEMO_COMMENT.format(traj_path=str(traj_path))
    with open(file, "w", encoding="utf-8") as f:
        f.write(f"{header}\n{content}")


def convert_traj_to_action_demo(traj_path: Path, output_file: Path, include_user: bool = False) -> None:
    with open(traj_path, encoding="utf-8") as file:
        traj = json.load(file)
    replay_config = traj["replay_config"]
    if isinstance(traj["replay_config"], str):
        replay_config = json.loads(traj["replay_config"])
    history = traj["history"]

    copy_fields = {"content", "role", "tool_calls", "agent", "message_type", "tool_call_ids"}

    admissible_roles = {"assistant", "user", "tool"} if include_user else {"assistant"}
    filtered_history = [
        {k: v for k, v in step.items() if k in copy_fields}
        for step in history
        if step["role"] in admissible_roles
        and step.get("agent", "main") in {"main", "primary"}
        and not step.get("is_demo")
    ]

    output_data = {"history": filtered_history, "replay_config": replay_config}
    save_demo(output_data, output_file, traj_path)
    logger.info(f"Saved demo to {output_file}")


def main(traj_path: Path, output_dir: Path, suffix: str = "", overwrite: bool = False, include_user: bool = False):
    output_file = output_dir / (traj_path.parent.name + suffix) / (traj_path.stem.removesuffix(".traj") + ".demo.yaml")
    if output_file.exists() and not overwrite:
        msg = f"Output file already exists: {output_file}. Use --overwrite to overwrite."
        raise FileExistsError(msg)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    convert_traj_to_action_demo(traj_path, output_file, include_user)


def run_from_cli(args: list[str] | None = None):
    """Convert a trajectory file to a demo file."""
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("traj_path", type=Path, help="Path to trajectory file")
    parser.add_argument("--output_dir", type=Path, help="Output directory for action demos", default=Path("./demos"))
    parser.add_argument("--suffix", type=str, help="Suffix for the output file", default="")
    parser.add_argument("--overwrite", help="Overwrite existing files", action="store_true")
    parser.add_argument(
        "--include_user",
        help="Include user responses (computer)",
        action="store_true",
    )
    parsed_args = parser.parse_args(args)
    main(**vars(parsed_args))


if __name__ == "__main__":
    run_from_cli()
