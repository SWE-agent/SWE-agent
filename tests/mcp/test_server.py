"""
Unit tests for the Model Context Protocol server implementation.

These tests verify the core functionality of the MCP server, including
command conversion, resource management, and protocol operations.
"""

import pytest

from sweagent.mcp.server import MCPResource, MCPServer, MCPTool
from sweagent.mcp.tools import command_to_mcp_tool
from sweagent.tools.commands import Command


def test_command_conversion():
    """Test conversion of Command objects to MCPTool objects."""
    command = Command(name="test_command", docstring="Test command description", arguments=[], function=lambda: None)
    tool = command_to_mcp_tool(command)

    assert tool.name == command.name
    assert tool.description == command.docstring


def test_command_conversion_with_parameters():
    """Test conversion of Command objects with parameters."""
    command = Command(
        name="test_params",
        docstring="Test command with parameters",
        arguments=[
            {"name": "arg1", "type": "string", "required": True},
            {"name": "arg2", "type": "integer", "required": False},
        ],
        function=lambda arg1, arg2=None: None,
    )
    tool = command_to_mcp_tool(command)

    assert "properties" in tool.parameters
    assert "arg1" in tool.parameters["properties"]
    assert "arg2" in tool.parameters["properties"]
    assert tool.parameters["required"] == ["arg1"]


def test_resource_registration():
    """Test resource registration and retrieval."""
    server = MCPServer()
    resource = MCPResource(uri="file:///test/path", content_type="text/plain", metadata={"type": "file"})

    server.register_resource(resource)
    retrieved = server.get_resource("file:///test/path")

    assert retrieved is not None
    assert retrieved.uri == resource.uri
    assert retrieved.content_type == resource.content_type
    assert retrieved.metadata == resource.metadata


def test_tool_registration():
    """Test tool registration and retrieval."""
    server = MCPServer()
    tool = MCPTool(
        name="test_tool", description="Test tool description", parameters={"type": "object", "properties": {}}
    )

    server.register_tool(tool)
    retrieved = server.get_tool("test_tool")

    assert retrieved is not None
    assert retrieved.name == tool.name
    assert retrieved.description == tool.description


def test_invalid_resource_uri():
    """Test handling of invalid resource URIs."""
    server = MCPServer()
    resource = server.get_resource("invalid://uri")
    assert resource is None


def test_missing_tool():
    """Test handling of missing tools."""
    server = MCPServer()
    tool = server.get_tool("nonexistent")
    assert tool is None


def test_resource_metadata_validation():
    """Test resource metadata validation."""
    with pytest.raises(ValueError):
        MCPResource(
            uri="file:///test",
            content_type="",  # Invalid empty content type
            metadata={"type": "file"},
        )


def test_tool_parameter_validation():
    """Test tool parameter validation."""
    with pytest.raises(ValueError):
        MCPTool(
            name="",  # Invalid empty name
            description="Test tool",
            parameters={"type": "object", "properties": {}},
        )
