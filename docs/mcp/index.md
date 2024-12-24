# Model Context Protocol (MCP) Server Implementation

The Model Context Protocol (MCP) server implementation in SWE-agent provides a standardized interface for agent-data source interactions while maintaining SWE-agent's existing optimizations and features.

## Overview

The MCP server implementation consists of several key components:

- **Server Core**: Handles resource and tool registration/management
- **Resource Management**: Provides standardized access to file system resources
- **Tool Integration**: Converts SWE-agent commands to MCP tools
- **ACI Features**: Maintains existing optimizations within MCP context

## Configuration

The MCP server is configured through `config/mcp.yaml`:

```yaml
server:
  host: localhost
  port: 8080

features:
  linting: true
  file_viewer: true
  search: true

resources:
  max_file_size: 10485760  # 10MB
  default_chunk_size: 100  # lines

tools:
  timeout: 30
  validate_commands: true
```

## Resource Management

Resources in the MCP server are identified by URIs and include metadata:

```python
resource = MCPResource(
    uri="file:///path/to/file",
    content_type="text/plain",
    metadata={"type": "file"}
)
```

### File Resources

File resources support optimized viewing and chunk-based access:

```python
content = server.view_file("file:///path/to/file", start=0, end=100)
```

## Tool Integration

SWE-agent commands are automatically converted to MCP tools:

```python
tool = command_to_mcp_tool(command)
server.register_tool(tool)
```

### Tool Parameters

Tools support parameter validation through JSON Schema:

```python
parameters = {
    "type": "object",
    "properties": {
        "arg1": {"type": "string"},
        "arg2": {"type": "integer"}
    },
    "required": ["arg1"]
}
```

## ACI Features

The MCP server maintains SWE-agent's core optimizations:

### Syntactic Linting

```python
errors = server.lint_code(code)
```

### File Viewing Optimization

```python
content = server.view_file(uri, start=0, end=100)  # 100-line chunks
```

### Directory Search

```python
matches = server.search_directory("*.txt", "/path/to/dir")
```

## Performance Considerations

The MCP server implementation maintains strict performance requirements:

- Directory search: < 1 second
- File viewing: < 0.5 seconds for 1MB files
- Linting: < 0.5 seconds for 100KB code blocks
- Tool registration: < 1 second for all commands

## Integration Example

```python
from sweagent.mcp.integration import ACIMCPServer

# Initialize server
server = ACIMCPServer()

# Register a file resource
resource = server.register_file("/path/to/file")

# View file contents
content = server.view_file(resource.uri)

# Search directory
matches = server.search_directory("*.py")

# Execute a tool
result = server.execute_tool("tool_name", {"arg1": "value"})
```

## Testing

The MCP implementation includes comprehensive test suites:

- Unit tests: `tests/mcp/test_server.py`
- Integration tests: `tests/mcp/test_integration.py`
- Performance tests: `tests/mcp/test_performance.py`

## Error Handling

The MCP server provides comprehensive error handling:

```python
try:
    content = server.view_file("file:///nonexistent")
except FileNotFoundError:
    # Handle missing file
except ValueError:
    # Handle invalid URI
```

## Future Considerations

- Support for additional resource types beyond files
- Extended tool parameter validation
- Enhanced performance optimizations
- Additional protocol features as needed
