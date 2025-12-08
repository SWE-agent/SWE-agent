# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SWE-agent is an AI software engineering agent that uses language models to autonomously fix issues in real GitHub repositories. The agent runs in sandboxed Docker containers (via SWE-ReX) and uses a tool-based architecture where the LM proposes actions that are executed in the environment.

**Key concepts:**
- **Agent**: Proposes actions based on problem statements (sweagent/agent/agents.py)
- **Environment (SWEEnv)**: Interfaces with SWE-ReX to execute commands in sandboxed containers (sweagent/environment/swe_env.py)
- **Tools/Bundles**: Command sets copied to containers and made available to the agent (tools/)
- **Trajectories**: Output files containing full agent execution traces (trajectories/)
- **Problem Statements**: Task definitions that can be GitHub issues, text, or datasets

## Development Commands

### Testing
```bash
# Run all tests
pytest

# Run tests in parallel
pytest -n auto

# Run specific test file
pytest tests/test_file.py

# Run with coverage
pytest --cov=sweagent
```

### Linting and Formatting
```bash
# Run pre-commit hooks (includes ruff linting and formatting)
pre-commit run --all-files

# Auto-fix with ruff
ruff check --fix .

# Format code
ruff format .
```

### Running SWE-agent

**Single instance (GitHub issue):**
```bash
sweagent run --config config/default.yaml --agent.model.name "gpt-4o" \
    --env.repo.github_url=https://github.com/owner/repo/ \
    --problem_statement.github_url=https://github.com/owner/repo/issues/123
```

**Local repository:**
```bash
sweagent run --config config/default.yaml --agent.model.name "gpt-4o" \
    --env.repo.path /path/to/repo \
    --problem_statement.path=path/to/problem_statement.md
```

**Batch mode (benchmarking):**
```bash
sweagent run-batch --config config/default.yaml --agent.model.name "gpt-4o" \
    --env.repo.repo_name=your_repo_name \
    --run.dataset_name=swe-bench/lite
```

**Other commands:**
```bash
sweagent inspect <trajectory_file>     # View trajectory in terminal
sweagent inspector                     # Web-based trajectory viewer
sweagent run-replay <trajectory_file>  # Replay a trajectory
```

## Architecture

### Core Components

**Entry points:** `sweagent/run/`
- `run_single.py`: Single-instance runs (GitHub issues, local repos)
- `run_batch.py`: Batch runs for benchmarking
- `run.py`: Main CLI dispatcher

**Agent system:** `sweagent/agent/`
- `agents.py`: Main agent class (`DefaultAgent`) that orchestrates LM interaction
- `models.py`: LM interface (supports OpenAI, Anthropic, etc. via litellm)
- `history_processors.py`: Process conversation history (caching, summarization)
- `problem_statement.py`: Problem statement handling (GitHub, text, datasets)

**Environment:** `sweagent/environment/`
- `swe_env.py`: Main `SWEEnv` class that interfaces with SWE-ReX
- `repo.py`: Repository cloning and management

**Tools:** `sweagent/tools/` and `tools/`
- Tool bundles are directories with config.yaml defining available commands
- Bundles are uploaded to containers and made available via $PATH
- Common bundles: `registry/`, `edit_anthropic/`, `review_on_submit_m/`

### Configuration System

Configurations are YAML files that define:
- **Agent templates**: System prompts, instance templates, step templates
- **Tools**: Which bundles to load, environment variables, parsing mode
- **Model**: LM name, cost limits, temperature
- **History processors**: Cache control, summarization

Example config structure:
```yaml
agent:
  templates:
    system_template: "You are a helpful assistant..."
    instance_template: "Problem: {{problem_statement}}"
  tools:
    bundles:
      - path: tools/registry
      - path: tools/edit_anthropic
    parse_function:
      type: function_calling
  model:
    name: gpt-4o
    per_instance_cost_limit: 3.0
```

### Multi-Agent Architecture

Recent additions include multi-agent support for complex tasks:
- **Agent Registry**: Manages multiple specialized agents (sweagent/agent/repair_framework.py)
- **Agent Adapters**: Wrap agents with role-based behavior (sweagent/agent/repair_adapters.py)
- **Coordinator**: Orchestrates multi-agent workflows
- **Sub-agents**: Agents created with `is_subagent=True` flag to share environments

See docs/multi_agent_quick_reference.md for usage patterns.

### Tool Parsing Modes

The agent supports multiple parsing modes for LM outputs:
- `function_calling`: Structured tool calls (recommended for capable models)
- `ThoughtActionParser`: Extracts thought/action pairs from text
- `ActionOnlyParser`: Expects direct action commands

## Code Conventions

From .cursor/rules/:
- Use Python 3.11+ with type annotations
- Use `pathlib` over `os.path`, prefer `Path.read_text()` over `open()` constructs
- Target Python 3.11 or higher
- Keep code comments minimal, highlight only complex logic
- Do not append to README unless specifically requested

## Key Dependencies

- **swe-rex**: Runtime environment for sandboxed execution (minimum 1.2.0)
- **litellm**: Unified LM API interface
- **pydantic**: Configuration and data validation
- **simple-parsing**: CLI argument parsing
- **unidiff**: Patch file handling

## Important Notes

- **SWE-ReX dependency**: This project requires SWE-ReX >=1.2.0. Environment interactions go through SWE-ReX's deployment abstraction (Docker, Modal, etc.)
- **Tool bundles**: Tools in `tools/` are copied to containers, not imported as Python modules
- **Trajectory files**: Always saved to `trajectories/` directory, contain full conversation history and metadata
- **Cost tracking**: Agents track per-instance costs and can be limited via `per_instance_cost_limit`
- **Docker images**: Default is `python:3.11` but configurable via `env.deployment.image`
