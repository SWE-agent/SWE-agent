"""
Integration tests for the Model Context Protocol server implementation.

These tests verify the integration between SWE-agent's ACI features and
the MCP server implementation, ensuring all optimizations are preserved.
"""

import os
import tempfile
from pathlib import Path

import pytest

from sweagent.mcp.integration import ACIMCPServer


def test_aci_features():
    """Test basic ACI features integration."""
    server = ACIMCPServer()
    result = server.features.lint_code("def test():\n    pass")
    assert len(result) == 0


def test_linting_with_errors():
    """Test linting feature with code containing errors."""
    server = ACIMCPServer()
    code = """def test():
        pass
    def broken():
    print('no indent')"""

    errors = server.lint_code(code)
    assert len(errors) > 0
    assert any("indentation" in error.lower() for error in errors)


def test_file_viewing():
    """Test file viewing optimization."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        # Create test file with 150 lines
        for i in range(150):
            f.write(f"Line {i}\n")
        temp_path = f.name

    try:
        server = ACIMCPServer()
        # Register the file
        resource = server.register_file(temp_path)

        # Test default 100-line chunk
        content = server.view_file(resource.uri)
        assert len(content.splitlines()) == 100

        # Test custom range
        content = server.view_file(resource.uri, start=50, end=75)
        assert len(content.splitlines()) == 25
        assert content.splitlines()[0].startswith("Line 50")
    finally:
        os.unlink(temp_path)


def test_directory_search():
    """Test directory search optimization."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test files
        for name in ["test1.txt", "test2.py", "other.txt"]:
            Path(temp_dir, name).touch()

        server = ACIMCPServer()

        # Test glob pattern
        matches = server.search_directory("*.txt", temp_dir)
        assert len(matches) == 2
        assert all(match.endswith(".txt") for match in matches)

        # Test regex pattern
        matches = server.search_directory("test.*", temp_dir)
        assert len(matches) == 2
        assert all("test" in match for match in matches)


def test_tool_execution():
    """Test tool execution through MCP server."""
    server = ACIMCPServer()
    server.load_commands()

    # Find a simple command to test
    test_tool = next((tool for tool in server.tools.values() if not tool.parameters), None)

    if test_tool:
        result = server.execute_tool(test_tool.name, {})
        assert result is not None


def test_resource_registration():
    """Test file resource registration and access."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("Test content")
        temp_path = f.name

    try:
        server = ACIMCPServer()
        resource = server.register_file(temp_path)

        assert resource.uri == f"file://{temp_path}"
        assert resource.content_type == "text/plain"
        assert resource.metadata["type"] == "file"
        assert resource.metadata["exists"] == "true"
    finally:
        os.unlink(temp_path)


def test_invalid_file_access():
    """Test error handling for invalid file access."""
    server = ACIMCPServer()

    with pytest.raises(FileNotFoundError):
        server.view_file("file:///nonexistent/path")

    with pytest.raises(ValueError):
        server.view_file("invalid://uri")


def test_search_invalid_directory():
    """Test error handling for invalid directory search."""
    server = ACIMCPServer()

    with pytest.raises(ValueError):
        server.search_directory("*.txt", "/nonexistent/path")
