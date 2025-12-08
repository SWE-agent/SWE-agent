# Multi-Agent Quick Reference

## Creating a Sub-Agent

```python
from sweagent.agent.agents import DefaultAgent, DefaultAgentConfig

# Option 1: From config with is_subagent flag
config = DefaultAgentConfig(...)
agent = DefaultAgent.from_config(config, is_subagent=True)

# Option 2: Direct instantiation
agent = DefaultAgent(
    templates=templates,
    tools=tools,
    model=model,
    is_subagent=True,  # Skips env initialization
)
```

## Creating an Agent Adapter

```python
from sweagent.agent.repair_adapters import SWEAgentAdapter, create_agent_adapter
from pathlib import Path

# Option 1: From YAML config
adapter = create_agent_adapter(
    role="topology",
    config_path=Path("config/repair/topology_agent.yaml")
)

# Option 2: With defaults
adapter = create_agent_adapter(role="topology")

# Option 3: Manual creation
config = DefaultAgentConfig(name="topology", role="topology", ...)
adapter = SWEAgentAdapter(name="topology", agent_config=config)
```

## Loading Multiple Agents

```python
from sweagent.agent.repair_adapters import load_repair_agent_configs
from pathlib import Path

# Load all *_agent.yaml configs from directory
configs = load_repair_agent_configs(Path("config/repair"))
# Returns: {"topology": DefaultAgentConfig, "contract": DefaultAgentConfig, ...}
```

## Setting Up Multi-Agent System

```python
from sweagent.agent.repair_framework import AgentRegistry, RepairCoordinator
from sweagent.environment.swe_env import SWEEnv

# 1. Create shared environment
env = SWEEnv(repo=repo)

# 2. Load configs
configs = load_repair_agent_configs(Path("config/repair"))

# 3. Register agents
registry = AgentRegistry()
for role, config in configs.items():
    adapter = SWEAgentAdapter(name=role, agent_config=config)
    adapter.setup(env=env)  # Share the environment
    registry.register(role, adapter)

# 4. Create coordinator and run
coordinator = RepairCoordinator(registry)
result = coordinator.run(repair_request)
```

## Creating Agent YAML Config

```yaml
name: topology          # Agent identifier
role: topology          # Role for history isolation
type: default           # Agent type

templates:
  system_template: |
    You are a Topology Analysis Agent...

  instance_template: |
    Repository: {{repo}}
    Problem: {{problem_statement}}

  next_step_template: |
    Observation: {{observation}}

model:
  name: claude-3-5-sonnet-20241022
  per_instance_cost_limit: 1.5
  temperature: 0.0
  top_p: 1.0

tools:
  execution_timeout: 120

max_requeries: 3
```

## Key Architectural Principles

1. **Environment Sharing**:
   - Primary agent creates environment
   - Sub-agents (is_subagent=True) reuse it

2. **Configuration Isolation**:
   - Always use `config.model_copy(deep=True)`
   - Each agent gets independent config

3. **Model Isolation**:
   - Each `from_config()` call creates new model instance
   - No shared state between agents

4. **History Isolation**:
   - Set `role` field in config
   - History automatically filtered by agent name

## Debugging Tips

```python
# Check if agent is sub-agent
assert agent.is_subagent == True

# Verify model independence
assert id(agent1.model) != id(agent2.model)

# Check history isolation
assert all(msg["agent"] == "topology" for msg in agent.messages)

# Verify environment sharing
assert adapter1.env is adapter2.env
```

## Common Patterns

### Pattern 1: Primary + Sub-Agents
```python
# Primary agent initializes environment
primary = DefaultAgent.from_config(primary_config)
primary.run(env, problem_statement)

# Sub-agents reuse environment
sub = DefaultAgent.from_config(sub_config, is_subagent=True)
sub.run(env, problem_statement)  # No env init
```

### Pattern 2: Coordinator with Adapters
```python
# Coordinator manages all agents
adapters = [
    SWEAgentAdapter("topology", topology_config),
    SWEAgentAdapter("contract", contract_config),
]

for adapter in adapters:
    adapter.setup(env=shared_env)
    registry.register(adapter.name, adapter)
```

### Pattern 3: Dynamic Agent Loading
```python
# Load agents based on issue type
if issue_type == "dependency":
    configs = load_repair_agent_configs(Path("config/dependency"))
elif issue_type == "security":
    configs = load_repair_agent_configs(Path("config/security"))
```

## Testing Checklist

- [ ] Sub-agent skips `tools.install()`
- [ ] Each agent has independent model config
- [ ] Each agent has independent model instance
- [ ] History properly filtered by agent name
- [ ] Environment shared across agents
- [ ] YAML configs load correctly

## Performance Considerations

1. **Memory**: Each agent has its own model instance (memory overhead)
2. **Cost**: Each agent makes independent LLM calls
3. **Time**: Agents run sequentially by default

## Optimization Tips

1. Use lower `per_instance_cost_limit` for specialized agents
2. Implement caching for repeated analyses
3. Consider parallel execution for independent agents
4. Reuse adapters across multiple repair requests

## Error Handling

```python
try:
    result = adapter.analyze(request)
except RuntimeError as e:
    if "not set up with environment" in str(e):
        adapter.setup(env=env)
        result = adapter.analyze(request)
```

## Directory Structure

```
sweagent/
├── agent/
│   ├── agents.py              # DefaultAgent with is_subagent support
│   ├── repair_adapters.py     # SWEAgentAdapter, config loaders
│   └── repair_framework.py    # AgentRegistry, RepairCoordinator
├── config/
│   └── repair/
│       ├── topology_agent.yaml
│       ├── contract_agent.yaml
│       └── ...
└── tools/
    └── multi_agent_demo_v2.py  # Complete example
```

---

**Quick Links**:
- Full Guide: `docs/multi_agent_implementation_guide.md`
- Architecture: `docs/multi_agent_refactoring_summary.md`
- Tests: `tests/test_multi_agent_refactoring.py`
- Demo: `tools/multi_agent_demo_v2.py`
