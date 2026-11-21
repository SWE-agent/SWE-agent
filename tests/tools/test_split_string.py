from __future__ import annotations

from tests.utils import make_python_tool_importable

make_python_tool_importable("tools/windowed/lib/flake8_utils.py", "flake8_utils")
from flake8_utils import Flake8Error, format_flake8_output  # type: ignore


def test_partition_flake8_line():
    assert Flake8Error.from_line("existing_lint error.py:12:41: E999 SyntaxError: invalid syntax") == Flake8Error(
        "existing_lint error.py", 12, 41, "E999 SyntaxError: invalid syntax"
    )


def test_partition_flake8_line_windows_absolute_path():
    # On Windows, flake8 emits lines like "C:\\Users\\dev\\app.py:12:5: F821 ...";
    # splitting the prefix on ":" breaks on the drive-letter colon.
    line = r"C:\Users\dev\project\app.py:12:5: F821 undefined name 'x'"
    assert Flake8Error.from_line(line) == Flake8Error(r"C:\Users\dev\project\app.py", 12, 5, "F821 undefined name 'x'")


def test_format_flake8_output_windows_absolute_path():
    output = format_flake8_output(r"C:\Users\dev\project\app.py:12:5: F821 undefined name 'x'")
    assert output == "- F821 undefined name 'x'"


def test_format_flake8_output_filters_previous_windows_path_errors():
    output = format_flake8_output(
        r"C:\Users\dev\project\app.py:20:5: F821 undefined name 'y'",
        previous_errors_string=r"C:\Users\dev\project\app.py:12:5: F821 undefined name 'x'",
        replacement_window=(12, 13),
        replacement_n_lines=3,
        show_line_numbers=True,
    )
    # The previous error sits inside the replaced window, so it must not be
    # subtracted from the new errors; the new error is still reported.
    assert output == "- line 20 col 5: F821 undefined name 'y'"


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
