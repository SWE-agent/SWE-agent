"""
ACI features implementation for the Model Context Protocol server.

This module provides implementations of SWE-agent's ACI optimizations within
the MCP server context, maintaining the efficiency and usability of the
original features while providing a standardized interface.
"""

import re
from pathlib import Path


class ACIFeatures:
    """
    Implementation of SWE-agent's ACI optimizations for the MCP server.

    This class maintains the core optimizations of SWE-agent's ACI while
    providing them through the MCP server interface:
    - Syntactic linting for edit commands
    - 100-line file viewing optimization
    - Efficient directory searching
    """

    def lint_code(self, code: str) -> list[str]:
        """
        Perform syntactic linting on code before edit commands.

        Args:
            code: The code to lint

        Returns:
            List of linting errors/warnings
        """
        errors = []

        # Basic syntax checks
        try:
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")

        # Indentation consistency check
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            if not line.strip():  # Skip empty lines
                continue

            # Check indentation
            indent = len(line) - len(line.lstrip())
            if indent % 4 != 0:
                errors.append(f"Line {i}: Indentation must be a multiple of 4 spaces")

            # Check for mixed tabs and spaces
            if "\t" in line[:indent]:
                errors.append(f"Line {i}: Mixed tabs and spaces in indentation")

        return errors

    def view_file(self, path: str, start: int = 0, end: int | None = None) -> str:
        """
        View file contents with 100-line optimization.

        Args:
            path: Path to the file
            start: Starting line number (0-based)
            end: Ending line number (exclusive), defaults to start + 100

        Returns:
            The requested portion of the file content

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If start/end are invalid
        """
        if not Path(path).exists():
            msg = f"File not found: {path}"
            raise FileNotFoundError(msg)
        if not Path(path).is_file():
            msg = f"Not a regular file: {path}"
            raise ValueError(msg)
        if start < 0:
            msg = "Start line cannot be negative"
            raise ValueError(msg)

        # Default to 100 lines if end is not specified
        if end is None:
            end = start + 100
        elif end <= start:
            msg = "End line must be greater than start line"
            raise ValueError(msg)

        with open(path) as f:
            # Skip lines until start
            for _ in range(start):
                next(f, None)

            # Read specified number of lines
            lines = []
            for _ in range(end - start):
                line = next(f, None)
                if line is None:
                    break
                lines.append(line)

            return "".join(lines)

    def search_directory(self, pattern: str, path: str = ".") -> list[str]:
        """
        Perform optimized directory search.

        Args:
            pattern: Search pattern (glob or regex)
            path: Directory to search in

        Returns:
            List of matching file paths

        Raises:
            ValueError: If path doesn't exist or pattern is invalid
        """
        if not Path(path).exists():
            msg = f"Directory not found: {path}"
            raise ValueError(msg)
        if not Path(path).is_dir():
            msg = f"Not a directory: {path}"
            raise ValueError(msg)

        try:
            # Try as regex first
            regex = re.compile(pattern)
            is_regex = True
        except re.error:
            # Fall back to glob
            is_regex = False

        matches = []
        base_path = Path(path)

        if is_regex:
            # Regex search
            for file_path in base_path.rglob("*"):
                if regex.search(str(file_path.relative_to(base_path))):
                    matches.append(str(file_path))
        else:
            # Glob search
            matches = [str(p) for p in base_path.glob(pattern)]

        return sorted(matches)  # Sort for consistent results
