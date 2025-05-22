#!/usr/bin/env python3
import sys
from typing import List

from windowed_file import WindowedFile  # type: ignore


def main(args: List[str]) -> int:
    if len(args) > 1:
        print("goto allows only one line number at a time.")
        return 1

    if not args:
        print("Usage: goto <line>")
        return 1

    try:
        line_number = int(args[0])
    except ValueError:
        print("Usage: goto <line>")
        print("Error: <line> must be a number")
        return 1

    wf = WindowedFile()

    if line_number > wf.n_lines:
        print(f"Error: <line> must be less than or equal to {wf.n_lines}")
        return 1

    # Convert from 1-based line numbers (user input) to 0-based (internal representation)
    wf.goto(line_number - 1, mode="top")
    wf.print_window()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
