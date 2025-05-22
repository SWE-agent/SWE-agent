from __future__ import annotations

from tests.utils import make_python_tool_importable

make_python_tool_importable("tools/windowed/lib/flake8_utils.py", "flake8_utils")
from flake8_utils import Flake8Error, format_flake8_output  # type: ignore


def test_partition_flake8_line():
    assert Flake8Error.from_line("existing_lint error.py:12:41: E999 SyntaxError: invalid syntax") == Flake8Error(
        "existing_lint error.py", 12, 41, "E999 SyntaxError: invalid syntax"
    )


# def test_update_previous_errors():
#     previous_errors = [
#         Flake8Error("existing_lint_error.py", 12, 41, "E999 SyntaxError: invalid syntax"),
#         Flake8Error("existing_lint_error.py", 15, 41, "E999 SyntaxError: invalid syntax"),
#         Flake8Error("existing_lint_error.py", 20, 41, "E999 SyntaxError: invalid syntax"),
#     ]
#     assert _update_previous_errors(previous_errors, (15, 18), 3) == [
#         Flake8Error("existing_lint_error.py", 12, 41, "E999 SyntaxError: invalid syntax"),
#         Flake8Error("existing_lint_error.py", 19, 41, "E999 SyntaxError: invalid syntax"),
#     ]
#     assert _update_previous_errors([], (15, 18), 3) == []


def test_flake8_format_no_error_1():
    assert (
        format_flake8_output(
            "a:12:41: e", previous_errors_string="a:12:41: e", replacement_window=(50, 51), replacement_n_lines=10
        )
        == ""
    )


def test_flake8_format_no_error_2():
    assert (
        format_flake8_output(
            "a:12:41: e", previous_errors_string="a:13:41: e", replacement_window=(1, 2), replacement_n_lines=1
        )
        == ""
    )


def test_flake8_format_no_error_3():
    assert (
        format_flake8_output(
            "a:12:41: e",
            previous_errors_string="a:13:41: e",
            replacement_window=(1, 2),
            replacement_n_lines=1,
            show_line_numbers=False,
        )
        == ""
    )


def test_flake8_format_error_1():
    assert (
        format_flake8_output(
            "a:12:41: e",
            previous_errors_string="a:13:41: e",
            replacement_window=(12, 13),
            replacement_n_lines=10,
            show_line_numbers=False,
        )
        == "- e"
    )


def test_flake8_format_error_1_linenumbers():
    assert (
        format_flake8_output(
            "a:12:41: e",
            previous_errors_string="a:13:41: e",
            replacement_window=(12, 13),
            replacement_n_lines=10,
            show_line_numbers=True,
        )
        == "- line 12 col 41: e"
    )
