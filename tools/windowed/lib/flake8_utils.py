#!/usr/bin/env python3

"""This helper command is used to parse and print flake8 output."""

# ruff: noqa: UP007 UP006 UP035

import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from sweagent import TOOLS_DIR
except ImportError:
    pass
else:
    import sys

    default_lib = TOOLS_DIR / "windowed" / "lib"
    assert default_lib.is_dir()
    sys.path.append(str(default_lib))
    sys.path.append(str(TOOLS_DIR / "registry" / "lib"))

from registry import registry


class Flake8Error:
    """A class to represent a single flake8 error"""

    def __init__(self, filename: str, line_number: int, col_number: int, problem: str):
        self.filename = filename
        self.line_number = line_number
        self.col_number = col_number
        self.problem = problem

    @classmethod
    def from_line(cls, line: str):
        try:
            prefix, _sep, problem = line.partition(": ")
            filename, line_number, col_number = prefix.split(":")
        except (ValueError, IndexError) as e:
            msg = f"Invalid flake8 error line: {line}"
            raise ValueError(msg) from e
        return cls(filename, int(line_number), int(col_number), problem)

    def __eq__(self, other):
        if not isinstance(other, Flake8Error):
            return NotImplemented
        return (
            self.filename == other.filename
            and self.line_number == other.line_number
            and self.col_number == other.col_number
            and self.problem == other.problem
        )

    def __repr__(self):
        return f"Flake8Error(filename={self.filename}, line_number={self.line_number}, col_number={self.col_number}, problem={self.problem})"


def _update_previous_errors(
    previous_errors: List[Flake8Error], replacement_window: Tuple[int, int], replacement_n_lines: int
) -> List[Flake8Error]:
    """Update the line numbers of the previous errors to what they would be after the edit window.
    This is a helper function for `_filter_previous_errors`.

    All previous errors that are inside of the edit window should not be ignored,
    so they are removed from the previous errors list.

    Args:
        previous_errors: list of errors with old line numbers
        replacement_window: the window of the edit/lines that will be replaced
        replacement_n_lines: the number of lines that will be used to replace the text

    Returns:
        list of errors with updated line numbers
    """
    updated = []
    lines_added = replacement_n_lines - (replacement_window[1] - replacement_window[0] + 1)
    for error in previous_errors:
        if error.line_number < replacement_window[0]:
            # no need to adjust the line number
            updated.append(error)
            continue
        if replacement_window[0] <= error.line_number <= replacement_window[1]:
            # The error is within the edit window, so let's not ignore it
            # either way (we wouldn't know how to adjust the line number anyway)
            continue
        # We're out of the edit window, so we need to adjust the line number
        updated.append(Flake8Error(error.filename, error.line_number + lines_added, error.col_number, error.problem))
    return updated


def format_flake8_output(
    input_string: str,
    show_line_numbers: bool = False,
    *,
    previous_errors_string: str = "",
    replacement_window: Optional[Tuple[int, int]] = None,
    replacement_n_lines: Optional[int] = None,
) -> str:
    """Filter flake8 output for previous errors and print it for a given file.

    Args:
        input_string: The flake8 output as a string
        show_line_numbers: Whether to show line numbers in the output
        previous_errors_string: The previous errors as a string
        replacement_window: The window of the edit (lines that will be replaced)
        replacement_n_lines: The number of lines used to replace the text

    Returns:
        The filtered flake8 output as a string
    """
    errors = [Flake8Error.from_line(line.strip()) for line in input_string.split("\n") if line.strip()]
    # print(f"New errors before filtering: {errors=}")
    lines = []
    if previous_errors_string:
        assert replacement_window is not None
        assert replacement_n_lines is not None
        previous_errors = [
            Flake8Error.from_line(line.strip()) for line in previous_errors_string.split("\n") if line.strip()
        ]
        # print(f"Previous errors before updating: {previous_errors=}")
        previous_errors = _update_previous_errors(previous_errors, replacement_window, replacement_n_lines)
        # print(f"Previous errors after updating: {previous_errors=}")
        errors = [error for error in errors if error not in previous_errors]
        # Sometimes new errors appear above the replacement window that were 'shadowed' by the previous errors
        # they still clearly aren't caused by the edit.
        errors = [error for error in errors if error.line_number >= replacement_window[0]]
        # print(f"New errors after filtering: {errors=}")
    for error in errors:
        if not show_line_numbers:
            lines.append(f"- {error.problem}")
        else:
            lines.append(f"- line {error.line_number} col {error.col_number}: {error.problem}")
    return "\n".join(lines)


def flake8(file_path: str) -> str:
    """Run flake8 on a given file and return the output as a string"""
    if Path(file_path).suffix != ".py":
        return ""
    cmd = registry.get("LINT_COMMAND", "flake8 --isolated --select=F821,F822,F831,E111,E112,E113,E999,E902 {file_path}")
    # don't use capture_output because it's not compatible with python3.6
    out = subprocess.run(cmd.format(file_path=file_path), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return out.stdout.decode()
