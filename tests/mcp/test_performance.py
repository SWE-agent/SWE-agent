"""
Performance tests for the Model Context Protocol server implementation.

These tests verify that the MCP server operations meet performance requirements
while maintaining SWE-agent's optimizations.
"""

import tempfile
import time
from pathlib import Path

from sweagent.mcp.integration import ACIMCPServer


def test_search_performance():
    """Test directory search performance meets requirements."""
    server = ACIMCPServer()
    start_time = time.time()
    server.features.search_directory("test")  # Remove unused results variable
    assert time.time() - start_time < 1.0  # Max 1s for search


def test_file_view_performance():
    """Test file viewing performance with large files."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        # Create a 1MB test file
        f.write("x" * 1024 * 1024)
        temp_path = f.name

    try:
        server = ACIMCPServer()
        resource = server.register_file(temp_path)

        start_time = time.time()
        server.view_file(resource.uri)  # Remove unused content variable
        assert time.time() - start_time < 0.5  # Max 0.5s for viewing
    finally:
        Path(temp_path).unlink()


def test_linting_performance():
    """Test code linting performance with large code blocks."""
    # Create a large code block (100KB)
    code = "def test():\n    pass\n" * 5000

    server = ACIMCPServer()
    start_time = time.time()
    server.lint_code(code)  # Remove unused errors variable
    assert time.time() - start_time < 0.5  # Max 0.5s for linting


def test_tool_registration_performance():
    """Test tool registration performance with many tools."""
    server = ACIMCPServer()
    start_time = time.time()
    server.load_commands()  # Load all available commands
    assert time.time() - start_time < 1.0  # Max 1s for loading all tools


def test_concurrent_operations():
    """Test performance under concurrent operations."""
    import concurrent.futures

    def run_operation():
        server = ACIMCPServer()
        server.search_directory("test")
        return True

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        start_time = time.time()
        futures = [executor.submit(run_operation) for _ in range(4)]
        results = [f.result() for f in futures]

        # All operations should complete within 2 seconds total
        assert time.time() - start_time < 2.0
        assert all(results)
