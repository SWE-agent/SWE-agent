"""
Integration layer for the Model Context Protocol server implementation.

This module provides the main integration point between SWE-agent's existing
ACI features and the MCP server interface, maintaining all optimizations
while providing a standardized protocol interface.
"""

from sweagent.tools.commands import get_available_commands

from .features import ACIFeatures
from .resources import FileResource
from .server import MCPServer
from .tools import command_to_mcp_tool


class ACIMCPServer(MCPServer):
    """
    MCP server implementation that integrates SWE-agent's ACI features.

    This class provides the main integration point between SWE-agent's
    existing command system and optimizations and the MCP protocol interface.
    It maintains all existing optimizations while providing a standardized
    way for agents to interact with the system.
    """

    def __init__(self):
        """Initialize the ACI MCP server with all features enabled."""
        super().__init__()
        self.features = ACIFeatures()
        self.load_commands()

    def load_commands(self) -> None:
        """
        Load all available SWE-agent commands as MCP tools.

        This method converts all existing SWE-agent commands to MCP tools
        while preserving their functionality and metadata.
        """
        for command in get_available_commands():
            tool = command_to_mcp_tool(command)
            self.register_tool(tool)

    def execute_tool(self, name: str, parameters: dict) -> dict:
        """
        Execute an MCP tool with the given parameters.

        Args:
            name: Name of the tool to execute
            parameters: Tool parameters

        Returns:
            Tool execution results

        Raises:
            ValueError: If tool doesn't exist or parameters are invalid
        """
        tool = self.get_tool(name)
        if tool is None:
            msg = f"Tool not found: {name}"
            raise ValueError(msg)

        # Find the original command
        commands = get_available_commands()
        command = next((cmd for cmd in commands if cmd.name == name), None)
        if command is None:
            msg = f"Command not found for tool: {name}"
            raise ValueError(msg)

        # Execute with proper parameter validation
        return command.execute(**parameters)

    def register_file(self, path: str) -> FileResource:
        """
        Register a file as an MCP resource.

        Args:
            path: Path to the file

        Returns:
            The registered FileResource

        Raises:
            ValueError: If path is invalid
        """
        resource = FileResource(path)
        self.register_resource(resource)
        return resource

    def lint_code(self, code: str) -> list[str]:
        """
        Perform syntactic linting using ACI features.

        Args:
            code: Code to lint

        Returns:
            List of linting errors/warnings
        """
        return self.features.lint_code(code)

    def view_file(self, uri: str, start: int = 0, end: int | None = None) -> str:
        """
        View file contents using ACI optimizations.

        Args:
            uri: Resource URI (file:// scheme)
            start: Starting line number
            end: Ending line number

        Returns:
            File contents

        Raises:
            ValueError: If URI is invalid or resource not found
        """
        if not uri.startswith("file://"):
            msg = "Only file:// URIs are supported"
            raise ValueError(msg)

        path = uri[7:]  # Remove file:// prefix
        return self.features.view_file(path, start, end)

    def search_directory(self, pattern: str, path: str = ".") -> list[str]:
        """
        Perform directory search using ACI optimizations.

        Args:
            pattern: Search pattern
            path: Directory to search in

        Returns:
            List of matching paths
        """
        return self.features.search_directory(pattern, path)
