"""
Resource management implementation for the Model Context Protocol server.

This module provides concrete resource implementations for the MCP server,
focusing on file system resources while maintaining SWE-agent's optimizations.
"""

from pathlib import Path

from .server import MCPResource


class FileResource(MCPResource):
    """
    Represents a file system resource in the MCP protocol.

    This implementation maintains SWE-agent's file viewing optimizations while
    providing a standard MCP interface for file access.

    Attributes:
        path: The filesystem path this resource represents
    """

    def __init__(self, path: str):
        """
        Initialize a file resource.

        Args:
            path: Filesystem path to the file
        """
        # Convert path to absolute and normalize
        abs_path = str(Path(path).resolve())

        super().__init__(
            uri=f"file://{abs_path}",
            content_type="text/plain",
            metadata={
                "type": "file",
                "path": abs_path,
                "exists": str(Path(abs_path).exists()).lower(),
                "is_file": str(Path(abs_path).is_file()).lower(),
            },
        )
        self.path = abs_path

    @property
    def exists(self) -> bool:
        """Check if the file exists."""
        return Path(self.path).exists()

    @property
    def is_file(self) -> bool:
        """Check if the path points to a regular file."""
        return Path(self.path).is_file()

    def read_chunk(self, start: int = 0, length: int | None = None) -> str:
        """
        Read a chunk of the file, maintaining SWE-agent's viewing optimization.

        Args:
            start: Starting line number (0-based)
            length: Maximum number of lines to read, None for all

        Returns:
            The requested portion of the file content

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If start is negative or length is negative
        """
        if not self.exists:
            msg = f"File not found: {self.path}"
            raise FileNotFoundError(msg)
        if not self.is_file:
            msg = f"Not a regular file: {self.path}"
            raise ValueError(msg)
        if start < 0:
            msg = "Start line cannot be negative"
            raise ValueError(msg)
        if length is not None and length < 0:
            msg = "Length cannot be negative"
            raise ValueError(msg)

        with open(self.path) as f:
            # Skip lines until start
            for _ in range(start):
                next(f, None)

            # Read specified number of lines
            if length is None:
                return f.read()

            lines = []
            for _ in range(length):
                line = next(f, None)
                if line is None:
                    break
                lines.append(line)

            return "".join(lines)
