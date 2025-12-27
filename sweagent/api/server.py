"""Flask API server for SWE-agent web interface."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO

# Import SWE-agent components
from sweagent.api.websocket_hook import WebSocketHook
from sweagent.run.run_single import RunSingleConfig
from sweagent.types import AgentRunResult


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global state for active runs
active_runs: Dict[str, Any] = {}
runs_lock = threading.Lock()


class RunState:
    """Track the state of a running SWE-agent instance."""
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.started = False
        self.completed = False
        self.error = None
        self.trajectory_steps: List[Dict[str, Any]] = []
        self.config = None
        self.problem_statement = ""
        self.exit_status = None
        self.model_stats = {}
        self.websocket_hook: Optional[WebSocketHook] = None
    
    def to_dict(self):
        return {
            "run_id": self.run_id,
            "started": self.started,
            "completed": self.completed,
            "error": self.error,
            "steps": len(self.trajectory_steps),
            "exit_status": self.exit_status,
            "model_stats": self.model_stats,
        }


def get_run_state(run_id: str) -> Optional[RunState]:
    """Get run state by ID."""
    with runs_lock:
        return active_runs.get(run_id)

def set_run_state(run_id: str, state: RunState):
    """Set run state by ID."""
    with runs_lock:
        active_runs[run_id] = state

def remove_run_state(run_id: str):
    """Remove run state by ID."""
    with runs_lock:
        if run_id in active_runs:
            del active_runs[run_id]

def generate_run_id() -> str:
    """Generate a unique run ID."""
    return f"run_{int(time.time() * 1000)}"


def _run_single_with_result(config: RunSingleConfig, websocket_hook: Optional[WebSocketHook] = None) -> AgentRunResult:
    """Wrapper around run_from_config that returns the result."""
    from sweagent.run.run_single import RunSingle
    
    # Create RunSingle instance from config
    run_single_instance = RunSingle.from_config(config)
    
    # Add WebSocket hook if provided
    if websocket_hook:
        run_single_instance.agent.add_hook(websocket_hook)
    
    # Run and return the result
    run_single_instance.run()

    data = run_single_instance.agent.get_trajectory_data()
    return AgentRunResult(info=data["info"], trajectory=data["trajectory"])



@app.route("/api/runs", methods=["GET"])
def list_runs():
    """List all active and completed runs."""
    with runs_lock:
        runs = [state.to_dict() for state in active_runs.values()]
    return jsonify({"runs": runs})


@app.route("/api/runs/<run_id>", methods=["GET"])
def get_run(run_id: str):
    """Get information about a specific run."""
    state = get_run_state(run_id)
    if not state:
        return jsonify({"error": f"Run {run_id} not found"}), 404
    
    return jsonify(state.to_dict())


@app.route("/api/runs/<run_id>/trajectory", methods=["GET"])
def get_trajectory(run_id: str):
    """Get the trajectory for a specific run."""
    state = get_run_state(run_id)
    if not state:
        return jsonify({"error": f"Run {run_id} not found"}), 404
    
    # Get trajectory from WebSocket hook if available, otherwise use stored steps
    trajectory_steps = []
    if state.websocket_hook and state.websocket_hook.trajectory_steps:
        trajectory_steps = state.websocket_hook.trajectory_steps
    elif state.trajectory_steps:
        trajectory_steps = state.trajectory_steps
    
    # Return the full trajectory with history
    result = {
        "trajectory": trajectory_steps,
        "problem_statement": state.problem_statement,
        "exit_status": state.exit_status,
        "model_stats": state.model_stats,
    }
    return jsonify(result)


def emit_update(run_id: str, event: str, data: Any):
    """Emit an update to all connected clients for a run."""
    socketio.emit(f"run_{run_id}_{event}", data)
    socketio.emit("update", {"run_id": run_id, **data})


def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries. Values from dict2 take precedence."""
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = deep_merge(result[key], value)
        else:
            # Override with value from dict2
            result[key] = value
    return result


def create_agent_config(problem_statement: str, config_path: Optional[str] = None, inline_config: Optional[Dict[str, Any]] = None) -> RunSingleConfig:
    """Create a configuration for the SWE-agent."""
    # Load default config
    config_dict = {
        "problem_statement": {}
    }
    
    # Handle different problem statement formats
    if isinstance(problem_statement, dict):
        # Problem statement is already a structured config (e.g., GitHub issue)
        config_dict["problem_statement"] = problem_statement
    elif isinstance(problem_statement, str):
        # Simple text problem statement
        config_dict["problem_statement"]["text"] = problem_statement
    
    # Determine which config file to use
    if not config_path:
        config_path = "./config/api_default.yaml"
    
    # Load from file and merge
    with open(config_path) as f:
        file_config = yaml.safe_load(f)
    
    # Merge configurations (file config takes precedence over our minimal config)
    config_dict = deep_merge(config_dict, file_config)
    
    # Apply inline configuration overrides if provided
    if inline_config:
        config_dict = deep_merge(config_dict, inline_config)
    
    return RunSingleConfig.model_validate(config_dict)


async def run_agent_async(run_id: str, problem_statement: str, config_path: Optional[str] = None, inline_config: Optional[Dict[str, Any]] = None):
    """Run SWE-agent asynchronously and emit updates via Socket.IO."""
    state = RunState(run_id)
    state.problem_statement = problem_statement
    set_run_state(run_id, state)
    
    try:
        # Emit start event
        emit_update(run_id, "start", {
            "run_id": run_id,
            "status": "started"
        })
        
        # Create config
        config = create_agent_config(problem_statement, config_path, inline_config)
        state.config = config
        
        # Create WebSocket hook and attach it to the state
        websocket_hook = WebSocketHook(run_id)
        websocket_hook._emit_function = emit_update
        state.websocket_hook = websocket_hook
        
        # Run the agent with the WebSocket hook in a separate thread
        result = await asyncio.to_thread(
            _run_single_with_result,
            config,
            websocket_hook,
        )
        
        # Update state with results from the hook if available
        if state.websocket_hook and state.websocket_hook.trajectory_steps:
            state.trajectory_steps = state.websocket_hook.trajectory_steps
        else:
            state.trajectory_steps = result.trajectory
            
        state.exit_status = result.info.get("exit_status")
        state.model_stats = result.info.get("model_stats", {})
        
        # Emit completion event
        emit_update(run_id, "complete", {
            "run_id": run_id,
            "status": "completed",
            "exit_status": state.exit_status,
            "steps": len(state.trajectory_steps),
            "model_stats": state.model_stats,
        })
        
    except Exception as e:
        logger.error(f"Error in run {run_id}: {e}")
        state.error = str(e)
        emit_update(run_id, "error", {
            "run_id": run_id,
            "status": "error",
            "error": str(e),
        })
    
    # Mark as completed but keep the state for retrieval
    state.completed = True


@app.route("/api/runs", methods=["POST"])
def create_run():
    """Create a new SWE-agent run."""
    data = request.get_json()
    
    if not data or "problem_statement" not in data:
        return jsonify({"error": "problem_statement is required"}), 400
    
    problem_statement = data["problem_statement"]
    config_path = data.get("config_path", "./config/api_default.yaml")
    inline_config = data.get("config")
    
    # Validate configuration if provided
    if inline_config:
        try:
            # Try to validate the structure
            test_config = RunSingleConfig.model_validate(inline_config)
        except Exception as e:
            return jsonify({
                "error": f"Invalid configuration: {str(e)}",
                "details": "Please check your configuration format and values."
            }), 400
    
    run_id = generate_run_id()
    
    # Start the agent in a background thread
    # Use threading to avoid async issues with Flask
    def start_agent_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_agent_async(run_id, problem_statement, config_path, inline_config))
        finally:
            loop.close()
    
    thread = threading.Thread(target=start_agent_task, daemon=True)
    thread.start()
    
    return jsonify({
        "run_id": run_id,
        "status": "started",
        "message": f"Run {run_id} started"
    }), 202


@app.route("/api/status", methods=["GET"])
def get_status():
    """Get server status."""
    return jsonify({
        "status": "running",
        "active_runs": len(active_runs),
        "timestamp": time.time(),
    })


@app.route("/api/config/schema", methods=["GET"])
def get_config_schema():
    """Get the configuration schema for SWE-agent."""
    try:
        # Get JSON schema from RunSingleConfig
        schema = RunSingleConfig.model_json_schema()
        
        return jsonify({
            "schema": schema,
            "description": "Configuration schema for SWE-agent runs. Use this to understand available options.",
            "example_configs": {
                "simple_text": {
                    "problem_statement": "Fix the bug in login.py",
                    "config": {
                        "agent": {
                            "model": {
                                "temperature": 0.7
                            }
                        }
                    }
                },
                "github_issue": {
                    "problem_statement": {
                        "type": "github",
                        "github_url": "https://github.com/owner/repo/issues/123"
                    }
                }
            }
        })
    except Exception as e:
        logger.error(f"Error generating config schema: {e}")
        return jsonify({"error": "Unable to generate configuration schema"}), 500


@app.route("/", methods=["GET"])
def serve_index():
    """Serve the main HTML page."""
    return send_from_directory(app.static_folder, "index.html")


@socketio.on("connect")
def handle_connect():
    """Handle client connection."""
    logger.info("Client connected")


@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnection."""
    logger.info("Client disconnected")


def get_parser() -> argparse.ArgumentParser:
    """Get argument parser for the API server."""
    parser = argparse.ArgumentParser(description="SWE-agent API Server")
    parser.add_argument("--port", type=int, default=5000, help="Port to run the server on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    return parser


async def main(args: Optional[List[str]] = None):
    """Main entry point for the API server."""
    parser = get_parser()
    args_parsed = parser.parse_args(args)
    
    logger.info(f"Starting SWE-agent API server on {args_parsed.host}:{args_parsed.port}")
    
    # Create static directory if it doesn't exist
    static_dir = Path(app.static_folder)
    static_dir.mkdir(exist_ok=True)
    
    try:
        socketio.run(
            app,
            host=args_parsed.host,
            port=args_parsed.port,
            debug=args_parsed.debug,
            use_reloader=False,
        )
    except KeyboardInterrupt:
        logger.info("Shutting down server...")


if __name__ == "__main__":
    asyncio.run(main())
