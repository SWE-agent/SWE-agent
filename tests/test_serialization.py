import pytest
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from sweagent.run.common import BasicCLI
from sweagent.utils.serialization import merge_nested_dicts


@pytest.mark.parametrize("previous", [None, "old", 0, False, ["old"]])
def test_merge_nested_dicts_replaces_non_mapping(previous):
    original = {"env": {"repo": previous, "keep": True}}

    result = merge_nested_dicts(original, {"env": {"repo": {"type": "preexisting"}}})

    assert result is original
    assert result == {"env": {"repo": {"type": "preexisting"}, "keep": True}}


def test_merge_nested_dicts_preserves_nested_keys():
    original = {"env": {"repo": {"type": "preexisting", "repo_name": "old"}}}

    merge_nested_dicts(original, {"env": {"repo": {"repo_name": "new"}}})

    assert original == {"env": {"repo": {"type": "preexisting", "repo_name": "new"}}}


def test_merge_nested_dicts_can_replace_mapping_with_none():
    assert merge_nested_dicts({"repo": {"repo_name": "testbed"}}, {"repo": None}) == {"repo": None}


def test_merge_nested_dicts_does_not_share_override_mappings():
    override = {"repo": {"settings": {"branch": "main"}}}
    result = merge_nested_dicts({"repo": None}, override)

    result["repo"]["settings"]["branch"] = "other"

    assert override == {"repo": {"settings": {"branch": "main"}}}


def test_cli_config_can_override_null_with_mapping(tmp_path):
    class RepoConfig(BaseModel):
        repo_name: str

    class Config(BaseSettings):
        repo: RepoConfig | None = None

    base = tmp_path / "base.yaml"
    override = tmp_path / "override.yaml"
    base.write_text("repo: null\n", encoding="utf-8")
    override.write_text("repo:\n  repo_name: testbed\n", encoding="utf-8")

    config = BasicCLI(Config).get_config(["--config", str(base), "--config", str(override)])

    assert config.repo == RepoConfig(repo_name="testbed")
