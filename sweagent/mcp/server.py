"""
Model Context Protocol (MCP) server implementation for SWE-agent.

This module provides the core server classes for implementing the Model Context Protocol,
which standardizes how AI agents interact with data sources. The implementation focuses
on maintaining SWE-agent's existing optimizations while providing a standard interface.
"""

from pydantic import BaseModel, Field


class MCPResource(BaseModel):
    """
    Represents a resource in the MCP protocol.

    Resources are addressable entities that can be accessed by URI and have associated
    metadata describing their properties.

    Attributes:
        uri: Unique identifier for the resource
        content_type: MIME type of the resource content
        metadata: Additional properties of the resource
    """

    uri: str = Field(..., description="Unique identifier for the resource")
    content_type: str = Field(..., description="MIME type of the resource content")
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional properties of the resource")


class MCPTool(BaseModel):
    """
    Represents a tool in the MCP protocol.

    Tools are callable functions that agents can use to interact with the system.
    They map directly to SWE-agent's existing command system.

    Attributes:
        name: Unique name of the tool
        description: Human-readable description of the tool's purpose
        parameters: Schema of the tool's parameters
    """

    name: str = Field(..., description="Unique name of the tool")
    description: str = Field(..., description="Human-readable description of the tool")
    parameters: dict[str, dict] = Field(default_factory=dict, description="Schema of the tool's parameters")


class MCPServer:
    """
    Main server class implementing the Model Context Protocol.

    This server maintains collections of resources and tools that can be accessed
    by AI agents through a standardized interface while preserving SWE-agent's
    existing optimizations.
    """

    def __init__(self):
        """Initialize an empty MCP server instance."""
        self.resources: dict[str, MCPResource] = {}
        self.tools: dict[str, MCPTool] = {}

    def register_resource(self, resource: MCPResource) -> None:
        """
        Register a new resource with the server.

        Args:
            resource: The MCPResource to register
        """
        self.resources[resource.uri] = resource

    def register_tool(self, tool: MCPTool) -> None:
        """
        Register a new tool with the server.

        Args:
            tool: The MCPTool to register
        """
        self.tools[tool.name] = tool

    def get_resource(self, uri: str) -> MCPResource | None:
        """
        Retrieve a resource by its URI.

        Args:
            uri: The URI of the resource to retrieve

        Returns:
            The requested resource or None if not found
        """
        return self.resources.get(uri)

    def get_tool(self, name: str) -> MCPTool | None:
        """
        Retrieve a tool by its name.

        Args:
            name: The name of the tool to retrieve

        Returns:
            The requested tool or None if not found
        """
        return self.tools.get(name)
