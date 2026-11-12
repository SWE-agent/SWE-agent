from __future__ import annotations

import json
from pathlib import Path

import yaml

from sweagent.run.run_traj_to_demo import convert_traj_to_action_demo


def _make_traj(path: Path, contents: list[str], *, ensure_ascii: bool = True) -> None:
    history = [
        {"role": "assistant", "content": content, "agent": "main", "message_type": "action"} for content in contents
    ]
    path.write_text(
        json.dumps(
            {"replay_config": {"agent": {"model": {"name": "test-model"}}}, "history": history},
            ensure_ascii=ensure_ascii,
        ),
        encoding="utf-8",
    )


def test_convert_traj_to_action_demo(tmp_path: Path) -> None:
    traj_path = tmp_path / "traj.traj"
    _make_traj(traj_path, ["I will inspect the repository.", "Running the tests."])
    demo_path = tmp_path / "traj.demo.yaml"
    convert_traj_to_action_demo(traj_path, demo_path)
    data = yaml.safe_load(demo_path.read_text(encoding="utf-8"))
    assert [step["content"] for step in data["history"]] == ["I will inspect the repository.", "Running the tests."]


def test_convert_traj_to_action_demo_unicode_content(tmp_path: Path) -> None:
    """Trajectory files written by other tools may contain raw UTF-8 non-ASCII.

    All file I/O must use an explicit UTF-8 encoding: with the platform default
    encoding (e.g., cp1252/cp936 on Windows), the trajectory was decoded with
    the legacy codepage (UnicodeDecodeError or silent mojibake) and the demo
    file was written in the legacy codepage instead of UTF-8.
    """
    traj_path = tmp_path / "traj.traj"
    _make_traj(traj_path, ["状态确认 \U0001f996"], ensure_ascii=False)
    demo_path = tmp_path / "traj.demo.yaml"
    convert_traj_to_action_demo(traj_path, demo_path)
    data = yaml.safe_load(demo_path.read_text(encoding="utf-8"))
    assert [step["content"] for step in data["history"]] == ["状态确认 \U0001f996"]


def test_convert_traj_to_action_demo_unicode_from_ascii_traj(tmp_path: Path) -> None:
    """SWE-agent writes .traj files with json.dumps' default ensure_ascii=True,
    so the file itself is pure ASCII even when model output contains Unicode.
    The demo file must still be written as UTF-8: with the platform default
    encoding (e.g., cp936 on Windows), writing the unicode content raised
    UnicodeEncodeError.
    """
    traj_path = tmp_path / "traj.traj"
    _make_traj(traj_path, ["All good \U0001f996 done"], ensure_ascii=True)
    demo_path = tmp_path / "traj.demo.yaml"
    convert_traj_to_action_demo(traj_path, demo_path)
    raw = demo_path.read_bytes()
    raw.decode("utf-8")  # demo file must be valid UTF-8
    data = yaml.safe_load(raw.decode("utf-8"))
    assert [step["content"] for step in data["history"]] == ["All good \U0001f996 done"]
