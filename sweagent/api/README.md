# SWE-agent Web Interface

A modern, responsive web interface for running SWE-agent with real-time progress updates.

## Features

- ✅ Modern, attractive UI with gradient design
- ✅ Real-time updates via WebSocket
- ✅ Chat-like interface showing agent progress
- ✅ Multiple runs tracking and management
- ✅ Detailed trajectory visualization
- ✅ Model statistics and exit status display
- ✅ Responsive design for mobile and desktop
- ✅ Error handling and recovery

## Installation

The web interface is included as part of the SWE-agent package. No additional installation is required.

## Usage

### Starting the Server

```bash
# Basic usage
python -m sweagent.api.server --port 5000 --host 0.0.0.0

# With debug mode (auto-reload)
python -m sweagent.api.server --port 5000 --debug

# Custom port
python -m sweagent.api.server --port 8080
```

### Accessing the Interface

Once the server is running, open your browser to:

```
http://localhost:5000
```

## API Endpoints

### GET /api/status
Get server status and information.

**Response:**
```json
{
  "status": "running",
  "active_runs": 0,
  "timestamp": 1234567890.123
}
```

### GET /api/runs
List all active and completed runs.

**Response:**
```json
{
  "runs": [
    {
      "run_id": "run_1234567890",
      "started": true,
      "completed": false,
      "error": null,
      "steps": 5,
      "exit_status": null,
      "model_stats": {}
    }
  ]
}
```

### POST /api/runs
Create a new SWE-agent run.

**Request Body:**
```json
{
  "problem_statement": "Fix the bug in the login function",
  "config_path": "/path/to/config.yaml"  // Optional
}
```

**Response:**
```json
{
  "run_id": "run_1234567890",
  "status": "started",
  "message": "Run run_1234567890 started"
}
```

### GET /api/runs/<run_id>
Get information about a specific run.

**Response:**
```json
{
  "run_id": "run_1234567890",
  "started": true,
  "completed": false,
  "error": null,
  "steps": 5,
  "exit_status": null,
  "model_stats": {}
}
```

### GET /api/runs/<run_id>/trajectory
Get the full trajectory for a specific run.

**Response:**
```json
{
  "trajectory": [
    {
      "thought": "Analyzing the problem...",
      "action": "Reading file login.py",
      "response": "File content read successfully",
      "observation": "def login(user, password): ..."
    }
  ],
  "problem_statement": "Fix the bug in the login function",
  "exit_status": null,
  "model_stats": {}
}
```

## WebSocket Events

The interface uses WebSocket for real-time updates:

### Connection
- `connect`: Client connected to server
- `disconnect`: Client disconnected from server

### Global Updates
- `update`: General update event with run information and detailed step data
  ```json
  {
    "run_id": "run_1234567890",
    "status": "running",
    "step_count": 1,
    "current_step": {
      "action": "Reading file requirements.txt",
      "observation": "File contains flask==2.0.0",
      "thought": "I need to understand the dependencies first",
      "response": "Successfully read file"
    },
    "model_stats": {
      "total_tokens": 1500.5,
      "cost_usd": 0.045
    }
  }
  ```

### Run-Specific Events
- `run_{run_id}_start`: Run started (status: running, step_count: 0)
- `run_{run_id}_step_start`: Step started (status: running, message: "Starting new step...")
- `run_{run_id}_actions_planned`: Actions being planned (status: running, message: "Planning: ...")
- `run_{run_id}_action_start`: Action starting (status: running, message: "Executing: ...")
- `run_{run_id}_step_complete`: Step completed (status: running, step_count: N, current_step: {...})
- `run_{run_id}_complete`: Run completed (status: completed, step_count: N, exit_status: "success")
- `run_{run_id}_error`: Run error occurred (status: error, error: "...")

## Configuration

You can customize the SWE-agent behavior in several ways:

### Method 1: Inline JSON Configuration

Pass configuration directly as JSON when creating a run:

```json
{
  "problem_statement": "Fix the bug in login.py",
  "config": {
    "agent": {
      "model": {
        "temperature": 0.7,
        "per_instance_cost_limit": 2.0
      }
    }
  }
}
```

### Method 2: Upload YAML Configuration File

Upload a YAML file through the web interface or reference it by path:

```yaml
# config.yaml
environment:
  type: "local"
  repo_dir: "/tmp/my_repo"
  reset_on_every_step: false

agent:
  model:
    temperature: 0.7
    per_instance_cost_limit: 2.0
```

Then pass it when creating a run:

```json
{
  "problem_statement": "Your problem here",
  "config_path": "/path/to/config.yaml"
}
```

### Method 3: Get Configuration Schema

To understand all available configuration options, fetch the schema:

```bash
curl http://localhost:5000/api/config/schema
```

This returns a complete JSON schema with all available fields and their descriptions.

### Configuration Examples

#### Simple Text Problem
```json
{
  "problem_statement": "Fix the bug in login.py"
}
```

#### GitHub Issue
```json
{
  "problem_statement": {
    "type": "github",
    "github_url": "https://github.com/owner/repo/issues/123"
  }
}
```

#### Custom Model Configuration
```json
{
  "problem_statement": "Implement feature X",
  "config": {
    "agent": {
      "model": {
        "name": "gpt-4o-mini",
        "temperature": 0.7,
        "per_instance_cost_limit": 3.0
      }
    }
  }
}
```

## Development

### Running in Debug Mode

```bash
python -m sweagent.api.server --port 5000 --debug
```

This enables:
- Auto-reload on code changes
- Debug output
- Interactive debugger on errors

### Testing

Run the standalone tests:

```bash
python test_web_standalone.py
```

## Browser Compatibility

The web interface is compatible with modern browsers:
- Chrome/Edge 80+
- Firefox 70+
- Safari 13+

## Troubleshooting

### Port already in use

If you get "Port already in use" error, either:
- Stop the process using that port
- Use a different port with `--port` flag

### Connection refused

Make sure the server is running and accessible at the specified host and port.

### WebSocket connection failed

Check browser console for errors. Ensure no ad-blockers or extensions are interfering with WebSocket connections.

## License

MIT License - see LICENSE in the root directory.
