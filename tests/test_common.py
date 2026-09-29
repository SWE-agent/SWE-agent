from __future__ import annotations

import pytest

from sweagent.run.common import _shorten_strings


def test_short_strings_are_left_alone():
    # A value that already fits the limit must not gain a trailing ellipsis.
    assert _shorten_strings("a") == "a"
    assert _shorten_strings("hello") == "hello"
    assert _shorten_strings("gpt-4o") == "gpt-4o"


def test_string_exactly_at_the_limit_is_left_alone():
    assert _shorten_strings("x" * 30) == "x" * 30


def test_long_strings_are_truncated_to_the_limit():
    out = _shorten_strings("y" * 31)

    assert out == "y" * 27 + "..."
    assert len(out) == 30


def test_custom_max_length_is_honored():
    assert _shorten_strings("short", max_length=10) == "short"
    assert _shorten_strings("z" * 11, max_length=10) == "z" * 7 + "..."


def test_newlines_are_escaped_before_measuring():
    assert _shorten_strings("a\nb") == "a\\nb"

    # The escaped form is 31 characters, so it is truncated even though the raw
    # input was only 30.
    assert _shorten_strings("x" * 29 + "\n") == "x" * 27 + "..."


def test_nested_long_strings_are_truncated():
    # The ellipsis rule applies at every level of nesting, not just at the top.
    out = _shorten_strings({"a": ["q" * 40, "short"]})

    assert out == {"a": ["q" * 27 + "...", "short"]}


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"model": {"name": "gpt-4o", "temperature": 0.0}}, {"model": {"name": "gpt-4o", "temperature": 0.0}}),
        (["short", "also-short"], ["short", "also-short"]),
        (42, 42),
        (None, None),
    ],
)
def test_non_string_values_pass_through(data, expected):
    # Nesting is walked, but non-strings are returned unchanged.
    assert _shorten_strings(data) == expected
