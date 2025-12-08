# MARRS - Multi-Agent Repository Repair System (Star Topology)

## Overview

MARRS implements a **Star Topology (Hub-and-Spoke)** architecture for multi-agent repository repair:

- **Hub (Coordinator)**: Central orchestrator that manages the shared environment and workflow
- **Spokes (Specialized Agents)**: RCA (Detective) and Patch (Developer) agents that only communicate with the Hub

## Architecture

```
User Input
    ↓
Coordinator (Hub) ← shared SWEEnv
    ↓
    ├─→ RCA Agent (Spoke 1) → Findings
    │                           ↓
    │                      Coordinator processes
    │                           ↓
    └─→ Patch Agent (Spoke 2) → Final Patch
```

## Key Design Principles

1. **Centralized Control**: Coordinator owns the SWEEnv and dispatches tasks
2. **No P2P Communication**: Agents never communicate directly with each other
3. **Context Injection**: Coordinator extracts RCA output and injects into Patch agent's prompt
4. **Shared Environment**: Single SWEEnv instance shared across all agents

## Components

### 1. Agent Configurations

- **`config/agents/rca_agent.yaml`**: RCA (Root Cause Analysis) agent config
  - Role: Detective - finds bugs and creates reproduction scripts
  - Constraint: CANNOT submit patches (analysis only)

- **`config/agents/patch_agent.yaml`**: Patch agent config
  - Role: Developer - implements fixes based on RCA findings
  - Goal: Pass tests and submit patches

### 2. Coordinator

- **`sweagent/agent/mas/coordinator.py`**: Star topology coordinator implementation
  - `RepairCoordinator` class: The Hub that orchestrates the workflow
  - Context management: Extracts and injects findings between agents
  - Environment lifecycle: Manages shared SWEEnv instance

### 3. Entry Point

- **`tools/run_mas.py`**: Command-line interface for running MARRS

## Usage

### Basic Usage

```bash
# Run on a GitHub issue
python tools/run_mas.py \
    --repo https://github.com/owner/repo \
    --issue https://github.com/owner/repo/issues/123

# Run on a local repository with text description
python tools/run_mas.py \
    --repo /path/to/local/repo \
    --issue_text "Bug description here"

# Run with issue from file
python tools/run_mas.py \
    --repo /path/to/repo \
    --issue_file issue_description.txt
```

### Options

```bash
--repo REPO               Repository URL or local path (required)
--issue ISSUE_URL         GitHub issue URL
--issue_text TEXT         Issue description as text
--issue_file FILE         Path to file with issue description
--rca_config PATH         RCA agent config (default: config/agents/rca_agent.yaml)
--patch_config PATH       Patch agent config (default: config/agents/patch_agent.yaml)
--output_dir DIR          Output directory (default: /tmp/marrs_output)
--docker_image IMAGE      Docker image (default: python:3.11)
--request_id ID           Request identifier (default: 'default')
```

## Workflow

1. **Environment Setup**: Coordinator creates shared SWEEnv instance
2. **RCA Phase (Spoke 1)**:
   - RCA agent analyzes repository
   - Creates reproduction script
   - Identifies root cause
   - Reports findings to Coordinator
3. **Hub Processing**: Coordinator extracts and processes RCA findings
4. **Patch Phase (Spoke 2)**:
   - Patch agent receives augmented context (issue + RCA findings)
   - Implements fix
   - Verifies with reproduction script
   - Submits patch
5. **Result Extraction**: Coordinator extracts final patch

## Testing

Run the test suite:

```bash
python tests/test_star_topology.py
```

Tests verify:
- Configuration loading from YAML files
- Coordinator instantiation with shared environment
- Agent config validation

## Implementation Details

### Environment Sharing

The key to the Star Topology is the `injected_env` parameter:

```python
# Coordinator creates environment
env = SWEEnv.from_config(env_config)

# Agents are created with injected environment
rca_agent = DefaultAgent.from_config(rca_config, injected_env=env)
patch_agent = DefaultAgent.from_config(patch_config, injected_env=env)
```

This ensures:
- Single environment instance shared across agents
- Agents skip environment initialization (already done)
- State persists between agent executions

### Context Injection

The Coordinator explicitly manages context flow:

```python
# 1. Extract findings from RCA agent
rca_findings = coordinator._extract_rca_findings(rca_result)

# 2. Build augmented prompt
augmented_prompt = coordinator._build_augmented_prompt(issue, rca_findings)

# 3. Pass to Patch agent
patch_result = patch_agent.run(problem_statement=augmented_prompt)
```

### Agent Isolation

- RCA agent: Blocked from using `submit` command
- Patch agent: Receives pre-processed context only through Coordinator
- No direct agent-to-agent communication

## Extending the System

To add a new specialized agent:

1. Create agent config YAML in `config/agents/`
2. Update `RepairCoordinator` to include new agent in workflow
3. Implement context extraction/injection logic in Coordinator

## Comparison to Previous Implementations

This Star Topology differs from earlier implementations:

- **Previous**: Linear chain with implicit context passing
- **Current**: Hub-and-Spoke with explicit Coordinator-managed context
- **Benefit**: Clear separation of concerns, explicit context control, easier debugging
