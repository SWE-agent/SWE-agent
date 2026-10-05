from __future__ import annotations

import pytest
import yaml

from sweagent.utils.serialization import merge_nested_dicts


@pytest.mark.parametrize("previous", [None, "disabled", ["old"], 0, False])
def test_mapping_overlay_replaces_non_mapping(previous):
    base = {"env": {"repo": previous}, "agent": {"max_steps": 10}}
    overlay = yaml.safe_load("env:\n  repo:\n    type: local\n    path: /tmp/project\n")
    assert merge_nested_dicts(base, overlay) is base
    assert base == {"env": {"repo": {"type": "local", "path": "/tmp/project"}}, "agent": {"max_steps": 10}}


def test_mapping_overlay_still_merges_existing_mapping():
    base = {"agent": {"model": {"name": "old", "temperature": 0}}}
    assert merge_nested_dicts(base, {"agent": {"model": {"name": "new"}}}) == {
        "agent": {"model": {"name": "new", "temperature": 0}}
    }


def test_scalar_overlay_replaces_mapping():
    base = {"env": {"repo": {"type": "local"}}}
    assert merge_nested_dicts(base, {"env": {"repo": None}}) == {"env": {"repo": None}}
