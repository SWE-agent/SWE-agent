from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from sweagent.run.run_replay import RunReplay
from sweagent.run.run_single import RunSingleConfig


def _replay(tmp_path: Path, updates: list[dict], saved: dict | None = None) -> RunReplay:
    config = RunSingleConfig.model_validate(
        saved
        or {
            "agent": {
                "model": {"name": "human"},
                "templates": {"system_template": "saved system", "instance_template": "saved instance"},
                "tools": {"parse_function": {"type": "thought_action"}},
                "history_processors": [{"type": "last_n_observations", "n": 7}],
                "max_requeries": 6,
            }
        }
    )
    replay = RunReplay.__new__(RunReplay)
    replay.traj_path = tmp_path / "example.traj"
    replay._replay_action_trajs_path = tmp_path / "actions.json"
    replay._update_config = []
    for index, update in enumerate(updates):
        path = tmp_path / f"update-{index}.yaml"
        path.write_text(json.dumps(update))
        replay._update_config.append(path)
    replay._traj_data = {
        "replay_config": config.model_dump(mode="json"),
        "history": [{"role": "assistant", "content": "```\necho example\n```"}],
    }
    replay.config = replay._get_config_from_agent(replay._traj_data)
    return replay


@pytest.mark.parametrize(
    "updates",
    [
        [],
        [{"agent": {}}],
        [{"agent": {"templates": {"system_template": "updated system"}}}],
        [{"agent": {"tools": {"execution_timeout": 123}}}],
        [
            {"agent": {"templates": {"system_template": "updated system"}}},
            {"agent": {"tools": {"execution_timeout": 123}}},
        ],
    ],
)
def test_replay_merges_nested_agent_updates(tmp_path, updates):
    replay = _replay(tmp_path, updates)
    agent = replay.config.agent
    assert agent.templates.instance_template == "saved instance"
    assert agent.tools.parse_function.type == "thought_action"
    assert agent.history_processors[0].type == "last_n_observations"
    assert agent.history_processors[0].n == 7
    assert agent.max_requeries == 6
    assert agent.model.name == "replay"
    if any("templates" in update["agent"] for update in updates):
        assert agent.templates.system_template == "updated system"
    if any("tools" in update["agent"] for update in updates):
        assert agent.tools.execution_timeout == 123
    replay._create_actions_file()
    assert json.loads(replay._replay_action_trajs_path.read_text())["example"] == [
        {"message": "```\necho example\n```"}
    ]


@pytest.mark.parametrize("repo", [None, {"type": "preexisting", "repo_name": "example"}])
def test_replay_replaces_optional_repo(tmp_path, repo):
    saved = {
        "agent": {"model": {"name": "human"}},
        "env": {"repo": None if repo else {"type": "preexisting", "repo_name": "saved"}},
    }
    config = _replay(tmp_path, [{"env": {"repo": repo}}], saved).config
    if repo is None:
        assert config.env.repo is None
    else:
        assert config.env.repo.type == "preexisting"
        assert config.env.repo.repo_name == "example"


def test_replay_replaces_problem_statement_variant(tmp_path):
    saved = {
        "agent": {"model": {"name": "human"}},
        "problem_statement": {
            "type": "github",
            "github_url": "https://github.com/SWE-agent/test-repo/issues/1",
            "id": "saved-id",
        },
    }
    config = _replay(tmp_path, [{"problem_statement": {"type": "text", "text": "replacement"}}], saved).config
    assert config.problem_statement.type == "text"
    assert config.problem_statement.text == "replacement"
    assert config.problem_statement.id == hashlib.sha256(b"replacement").hexdigest()[:6]


def test_replay_replaces_deployment_variant_without_creating_deployment(tmp_path):
    config = _replay(tmp_path, [{"env": {"deployment": {"type": "local"}}}]).config
    assert config.env.deployment.type == "local"


def test_replay_replaces_explicit_model_variant(tmp_path):
    saved = {"agent": {"model": {"name": "replay", "replay_path": "old.json"}}}
    config = _replay(tmp_path, [{"agent": {"model": {"name": "human"}}}], saved).config
    assert config.agent.model.name == "replay"


def test_replay_replaces_history_processor_list(tmp_path):
    config = _replay(tmp_path, [{"agent": {"history_processors": []}}]).config
    assert config.agent.history_processors == []
