from __future__ import annotations

from pathlib import Path

from sweagent import __version__

ROOT = Path(__file__).resolve().parent.parent


def test_version():
    assert __version__.count(".") == 2


def test_tool_patch_readers_preserve_newlines():
    for script in [
        ROOT / "tools" / "review_on_submit_m" / "bin" / "submit",
        ROOT / "tools" / "diff_state" / "bin" / "_state_diff_state",
    ]:
        assert 'newline=""' in script.read_text()
