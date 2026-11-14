import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from sweagent.agent.agents import DefaultAgent, RetryAgent, TemplateConfig
from sweagent.agent.models import InstanceStats


@pytest.fixture(params=["default", "retry", "retry-selected"])
def checkpoint(request, tmp_path, monkeypatch):
    target = tmp_path / "instance.traj"
    data = {"trajectory": [], "history": [], "info": {}, "replay_config": None, "environment": "test"}
    if request.param == "default":
        agent = DefaultAgent(templates=TemplateConfig(), tools=Mock(), history_processors=[], model=Mock())
        agent.traj_path = target
        monkeypatch.setattr(agent, "get_trajectory_data", lambda: data)

        def expected():
            return data

        return target, data, agent.save_trajectory, expected

    agent = RetryAgent(config=Mock())
    agent._traj_path = target
    agent._attempt_data = [data]
    agent._rloop = SimpleNamespace(get_best=lambda: 0, review_model_stats=InstanceStats())
    choose = request.param == "retry-selected"

    def expected():
        if not choose:
            return {"attempts": [data]}
        stats = InstanceStats().model_dump()
        return {
            "attempts": [data],
            "trajectory": data["trajectory"],
            "history": [],
            "info": {
                "best_attempt_idx": 0,
                "rloop_model_stats": stats,
                "model_stats": (InstanceStats() + InstanceStats()).model_dump(),
            },
            "replay_config": None,
            "environment": "test",
        }

    return target, data, lambda: agent.save_trajectory(choose=choose), expected


def test_checkpoint_retains_complete_json_after_interrupted_write(checkpoint, monkeypatch):
    target, data, save, expected = checkpoint
    save()
    previous = target.read_bytes()
    original_write = Path.write_text
    interruption = KeyboardInterrupt()

    def interrupt_after_prefix(path, text, *args, **kwargs):
        original_write(path, text[:10], *args, **kwargs)
        raise interruption

    data["trajectory"].append({"observation": "another step"})
    with monkeypatch.context() as patch:
        patch.setattr(Path, "write_text", interrupt_after_prefix)
        with pytest.raises(KeyboardInterrupt) as caught:
            save()

    assert caught.value is interruption
    assert target.read_bytes() == previous
    assert list(target.parent.iterdir()) == [target]

    save()
    assert target.read_text() == json.dumps(expected(), indent=2)
    assert list(target.parent.iterdir()) == [target]


def test_checkpoint_reader_sees_previous_contents_until_replace(checkpoint, monkeypatch):
    target, data, save, expected = checkpoint
    save()
    previous = target.read_text()
    data["trajectory"].append({"observation": "another step"})
    original_replace = Path.replace
    replaced = []

    def inspect_before_replace(staged, destination):
        assert target.read_text() == previous
        assert staged.read_text() == json.dumps(expected(), indent=2)
        assert list(target.parent.glob("*.traj")) == [target]
        replaced.append(destination)
        return original_replace(staged, destination)

    monkeypatch.setattr(Path, "replace", inspect_before_replace)
    save()
    assert replaced == [target]
    assert target.read_text() == json.dumps(expected(), indent=2)


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes and symbolic links")
def test_checkpoint_preserves_symlink_target_and_mode(checkpoint):
    target, data, save, expected = checkpoint
    actual = target.with_name("actual.traj")
    target.symlink_to(actual.name)
    mask = os.umask(0o027)
    try:
        save()
    finally:
        os.umask(mask)

    assert stat.S_IMODE(actual.stat().st_mode) == 0o640
    actual.chmod(0o600)
    data["trajectory"].append({"observation": "another step"})
    save()
    assert target.is_symlink()
    assert actual.read_text() == json.dumps(expected(), indent=2)
    assert stat.S_IMODE(actual.stat().st_mode) == 0o600


@pytest.mark.skipif(os.name != "posix", reason="POSIX link and file permissions")
def test_checkpoint_preserves_shared_inode(checkpoint):
    target, data, save, expected = checkpoint
    save()
    alias = target.with_name("alias.traj")
    alias.hardlink_to(target)
    data["trajectory"].append({"observation": "another step"})

    save()

    assert alias.samefile(target)
    assert alias.read_text() == json.dumps(expected(), indent=2)
