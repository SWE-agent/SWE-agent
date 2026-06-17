"""Tests for ``ToolHandler.should_block_action``.

The blocklist is a reliability filter that stops the agent from launching
interactive / long-running programs (``vim``, ``less``, ``tail -f``, a bare
``python`` REPL, ...) that would hang the run loop. These tests pin down that the
filter inspects every command in a compound command line and normalizes
path-qualified / wrapper-prefixed invocations, so a blocked program cannot slip
through simply by being written as ``/usr/bin/vim``, ``env vim`` or ``true; vim``.
"""

from __future__ import annotations

import pytest

from sweagent.tools.parsing import FunctionCallingParser
from sweagent.tools.tools import ToolConfig, ToolHandler


@pytest.fixture
def handler() -> ToolHandler:
    return ToolHandler(ToolConfig(parse_function=FunctionCallingParser()))


@pytest.mark.parametrize(
    "action",
    [
        # bare forms (already blocked before the hardening)
        "vim",
        "python",
        "tail -f log",
        # path-qualified forms
        "/usr/bin/vim file",
        "/bin/sh",
        # wrapper-prefixed forms
        "env vim",
        "env -i vim",
        "FOO=bar /usr/bin/vim",
        "sudo nano /etc/hosts",
        "nice vim",
        # operator-wrapped / compound forms
        "x && vim",
        "true; vim",
        "echo hi | less",
        "echo a || vim",
        "cat f && less g",
        "ls; tail -f log",
        # command substitution
        "$(vim)",
        "`vim`",
        "echo $(vim) done",
    ],
)
def test_blocked_invocations(handler: ToolHandler, action: str):
    assert handler.should_block_action(action) is True


@pytest.mark.parametrize(
    "action",
    [
        # ordinary, non-interactive commands must stay allowed
        "ls -l",
        "echo ok",
        "cat file.py",
        "grep -r foo .",
        "git status",
        # a blocklisted name as a *quoted argument* is not an invocation of it
        'echo "a && vim"',
        'grep "make" f',
        'echo "tail -f"',
        "git commit -m 'x; vim'",
        # blocklisted names used as non-interactive subcommands stay allowed
        "python script.py",
        # radare2 is allowed when invoked with -c (existing block_unless_regex rule)
        "radare2 -c px /bin/ls",
    ],
)
def test_allowed_invocations(handler: ToolHandler, action: str):
    assert handler.should_block_action(action) is False


def test_empty_action_not_blocked(handler: ToolHandler):
    assert handler.should_block_action("") is False
    assert handler.should_block_action("   ") is False
