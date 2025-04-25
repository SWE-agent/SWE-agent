#!/usr/bin/env python3
import sys
from pathlib import Path

from windowed_file import WindowedFile  # type: ignore


def main():
    if len(sys.argv) < 2:
        print("Usage: create <filename>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.parent.is_dir():
        path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        print(f"Warning: File '{path}' already exists.")
        sys.exit(1)

    path.touch()

    wfile = WindowedFile(path=path)
    wfile.first_line = 0
    wfile.print_window()


if __name__ == "__main__":
    main()
