"""
Tool mapping implementation for the Model Context Protocol server.

This module provides functionality to convert SWE-agent commands to MCP tools,
maintaining compatibility with the existing command system while providing
a standardized MCP interface.
"""

from sweagent.tools.commands import Command

from .server import MCPTool


def command_to_mcp_tool(command: Command) -> MCPTool:
    """
    Convert a SWE-agent Command to an MCP tool.

    This function maps SWE-agent's command system to the MCP tool interface,
    preserving all command metadata and functionality.

    Args:
        command: The Command object to convert

    Returns:
        An MCPTool representing the command
    """
    # Get the OpenAI function calling tool definition
    tool_def = command.get_function_calling_tool()

    return MCPTool(
        name=command.name, description=command.docstring or "", parameters=tool_def["function"]["parameters"]
    )


class ToolRegistry:
    """
    Registry for managing MCP tools converted from SWE-agent commands.

    This class maintains a mapping of command names to their MCP tool
    representations and handles tool registration and lookup.
    """

    def __init__(self):
        """Initialize an empty tool registry."""
        self._tools: dict[str, MCPTool] = {}

    def register_command(self, command: Command) -> None:
        """
        Register a command as an MCP tool.

        Args:
            command: The Command object to register
        """
        tool = command_to_mcp_tool(command)
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> MCPTool | None:
        """
        Retrieve a tool by name.

        Args:
            name: The name of the tool to retrieve

        Returns:
            The requested tool or None if not found
        """
        return self._tools.get(name)

    def list_tools(self) -> dict[str, MCPTool]:
        """
        Get all registered tools.

        Returns:
            A dictionary mapping tool names to MCPTool objects
        """
        return self._tools.copy()
