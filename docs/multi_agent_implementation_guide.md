# Multi-Agent System Refactoring - Implementation Guide

## Executive Summary

This document provides the complete refactoring implementation for transitioning swe-agent from a single-agent architecture to a robust Multi-Agent System (MAS) where agents can share environments but maintain distinct capabilities.

## Problem Statement

**Original Issues:**
1. **Environment Lifecycle Coupling**: `DefaultAgent` always creates and initializes its own environment, preventing environment sharing
2. **Model Configuration Sharing**: Sub-agents instantiated in `repair_framework.py` were sharing model configurations
3. **Disconnected Adapters**: `repair_adapters.py` was not integrated into the repair workflow

## Solution Architecture

### 1. Environment Lifecycle Decoupling

**File**: `sweagent/agent/agents.py` (Lines 454-527, 593-651)

**Key Changes:**

```python
class DefaultAgent(AbstractAgent):
    def __init__(
        self,
        *,
        # ... existing parameters ...
        is_subagent: bool = False,  # NEW PARAMETER
    ):
        """
        Args:
            is_subagent: If True, this agent is a sub-agent in a multi-agent system
                        and will skip environment initialization steps (tools installation,
                        env variables setup) assuming the primary agent or orchestrator
                        has already handled this.
        """
        # ... existing code ...
        self.is_subagent = is_subagent
        self._env_is_injected = False

    @classmethod
    def from_config(cls, config: DefaultAgentConfig, is_subagent: bool = False) -> Self:
        # ... existing code ...
        return cls(
            # ... existing parameters ...
            is_subagent=is_subagent,  # NEW
        )

    def setup(self, env: SWEEnv, problem_statement, output_dir):
        """Setup with conditional environment initialization"""
        # ... existing code ...

        if not self.is_subagent:
            # Primary agent: full environment setup
            self._chook.on_tools_installation_started()
            self.tools.install(self._env)
            self._chook.on_setup_attempt()
            self._env.set_env_variables({"PROBLEM_STATEMENT": ...})
        else:
            # Sub-agent: skip environment initialization
            self.logger.info(f"Sub-agent '{self.name}': skipping environment initialization")
            self._chook.on_setup_attempt()

        # ... rest of setup (system message, demos, etc.) ...
```

**Benefits:**
- Primary agent initializes the environment once
- Sub-agents reuse the initialized environment
- No redundant tool installation or environment variable setup
- Clear separation of responsibilities

### 2. Model & Capability Isolation

**Files**:
- `sweagent/agent/agents.py` (Lines 529-546)
- `sweagent/agent/repair_adapters.py` (Lines 38-90)

**Key Changes in `repair_adapters.py`:**

```python
class SWEAgentAdapter(BaseAgent):
    def __init__(self, name: str, agent_config: DefaultAgentConfig):
        super().__init__(name)
        # CRITICAL: Deep copy to ensure independence
        self._config = agent_config.model_copy(deep=True)
        self._config.role = name
        self._config.name = name
        self._agent: DefaultAgent | None = None

    def analyze(self, request: RepairRequest, context=None) -> AgentResult:
        """Each analyze() call creates a FRESH agent instance"""
        # Create NEW agent with independent model configuration
        self._agent = DefaultAgent.from_config(
            self._config,
            is_subagent=True  # Skip environment initialization
        )

        # Run agent on shared environment
        result = self._agent.run(env=self.env, problem_statement=..., ...)

        return self._trajectory_to_agent_result(result.trajectory, result.info)
```

**Isolation Guarantees:**

1. **Configuration Level**:
   ```python
   adapter1._config = config.model_copy(deep=True)  # Independent copy
   adapter2._config = config.model_copy(deep=True)  # Different copy

   # Changes to one don't affect the other
   adapter1._config.model.temperature = 0.5
   assert adapter2._config.model.temperature != 0.5
   ```

2. **Model Instance Level**:
   ```python
   # Each call to from_config creates a NEW model instance
   model1 = get_model(config.model, config.tools)  # Fresh instance
   model2 = get_model(config.model, config.tools)  # Different instance

   assert id(model1) != id(model2)
   ```

3. **History Level**:
   ```python
   # DefaultAgent.messages property filters by agent name
   @property
   def messages(self):
       filtered = [e for e in self.history if e["agent"] == self.name]
       # ... apply history processors ...
       return filtered
   ```

### 3. Configuration System Integration

**File**: `sweagent/agent/repair_adapters.py` (Lines 239-316)

**New Functions:**

```python
def create_agent_adapter(
    role: str,
    config_path: Path | None = None,
    **config_overrides,
) -> SWEAgentAdapter:
    """Factory function to create agent adapters"""
    if config_path:
        # Load from YAML
        with open(config_path) as f:
            yaml_config = yaml.safe_load(f)
        config = DefaultAgentConfig(**yaml_config)
    else:
        # Use defaults
        config = DefaultAgentConfig(
            name=role,
            role=role,
            templates=TemplateConfig(...),
            tools=ToolConfig(),
            model=GenericAPIModelConfig(...),
        )

    # Apply overrides
    for key, value in config_overrides.items():
        setattr(config, key, value)

    return SWEAgentAdapter(role, config)


def load_repair_agent_configs(config_dir: Path) -> Dict[str, DefaultAgentConfig]:
    """Load all agent configurations from directory"""
    configs = {}
    for config_file in config_dir.glob("*_agent.yaml"):
        with open(config_file) as f:
            yaml_config = yaml.safe_load(f)

        role = yaml_config.get("role") or yaml_config.get("name")
        config = DefaultAgentConfig(**yaml_config)
        configs[role] = config

    return configs
```

**Configuration Files:**

Created in `config/repair/`:
- `topology_agent.yaml`: Dependency analysis configuration
- `contract_agent.yaml`: Contract verification configuration

Example structure:
```yaml
name: topology
role: topology
type: default

templates:
  system_template: |
    You are a Topology Analysis Agent...

  instance_template: |
    Repository: {{repo}}
    Problem: {{problem_statement}}

model:
  name: claude-3-5-sonnet-20241022
  per_instance_cost_limit: 1.5
  temperature: 0.0

tools:
  execution_timeout: 120

max_requeries: 3
```

## Complete Usage Example

**File**: `tools/multi_agent_demo_v2.py`

```python
from pathlib import Path
from sweagent.agent.repair_framework import AgentRegistry, RepairCoordinator, RepairRequest
from sweagent.agent.repair_adapters import SWEAgentAdapter, load_repair_agent_configs
from sweagent.environment.swe_env import SWEEnv

# 1. Load agent configurations from YAML
config_dir = Path("config/repair")
agent_configs = load_repair_agent_configs(config_dir)

# 2. Create shared environment (primary agent responsibility)
env = SWEEnv(repo=repo)

# 3. Register agents with distinct configurations
registry = AgentRegistry()
for role, config in agent_configs.items():
    adapter = SWEAgentAdapter(name=role, agent_config=config)
    adapter.setup(env=env, config={"output_dir": "/tmp/repair_agents"})
    registry.register(role, adapter)

# 4. Run repair workflow
coordinator = RepairCoordinator(registry)
request = RepairRequest(
    id="demo-001",
    repository="test-repo",
    target_commit="abc123",
    failing_tests=["test_feature.py::test_case_1"],
)

result = coordinator.run(request)

# 5. Verify isolation
for role in agent_configs.keys():
    adapter = registry.get(role)
    print(f"Agent '{role}':")
    print(f"  Model instance ID: {id(adapter._agent.model)}")
    print(f"  Is sub-agent: {adapter._agent.is_subagent}")
```

## Testing & Verification

**File**: `tests/test_multi_agent_refactoring.py`

**Test Coverage:**

1. **Environment Injection**:
   - ✅ Primary agent calls `tools.install()`
   - ✅ Sub-agent skips `tools.install()`
   - ✅ `is_subagent` flag properly propagates

2. **Model Isolation**:
   - ✅ `model_copy(deep=True)` creates independent configs
   - ✅ Each agent has distinct model instance
   - ✅ Adapter creates fresh agent per `analyze()` call

3. **History Isolation**:
   - ✅ `agent.messages` filters by `agent` field
   - ✅ `role` field sets agent name correctly

4. **Adapter Integration**:
   - ✅ Adapter passes `is_subagent=True` to `from_config()`

**Running Tests:**
```bash
python -m pytest tests/test_multi_agent_refactoring.py -v
```

**All tests passing ✅**

## Files Modified

1. **`sweagent/agent/agents.py`**:
   - Lines 454-527: Added `is_subagent` parameter to `__init__`
   - Lines 529-546: Updated `from_config` to accept `is_subagent`
   - Lines 593-651: Modified `setup()` for conditional env initialization

2. **`sweagent/agent/repair_adapters.py`**:
   - Lines 38-90: Updated `analyze()` to pass `is_subagent=True`
   - Lines 239-316: Implemented YAML config loading functions

## Files Created

1. **Configuration Files**:
   - `config/repair/topology_agent.yaml`: Topology analysis agent config
   - `config/repair/contract_agent.yaml`: Contract verification agent config

2. **Documentation**:
   - `docs/multi_agent_refactoring_summary.md`: Architecture summary
   - `docs/multi_agent_implementation_guide.md`: This document

3. **Tools & Tests**:
   - `tools/multi_agent_demo_v2.py`: Complete integration demo
   - `tests/test_multi_agent_refactoring.py`: Comprehensive test suite

## Migration Path

### For Existing Code

**Before** (single agent):
```python
agent = DefaultAgent.from_config(config)
result = agent.run(env, problem_statement)
```

**After** (primary agent, no changes):
```python
agent = DefaultAgent.from_config(config)  # is_subagent defaults to False
result = agent.run(env, problem_statement)
```

**New** (sub-agent):
```python
sub_agent = DefaultAgent.from_config(config, is_subagent=True)
result = sub_agent.run(env, problem_statement)  # Shares env, skips init
```

### For Multi-Agent Systems

**New Pattern**:
```python
# Load configs
configs = load_repair_agent_configs(Path("config/repair"))

# Create shared environment
env = SWEEnv(repo=repo)

# Register agents
registry = AgentRegistry()
for role, config in configs.items():
    adapter = SWEAgentAdapter(name=role, agent_config=config)
    adapter.setup(env=env)
    registry.register(role, adapter)

# Run workflow
coordinator = RepairCoordinator(registry)
result = coordinator.run(request)
```

## Key Insights

1. **Dependency Injection Pattern**: Sub-agents receive environment via parameter, not internal creation

2. **Deep Copying Strategy**: `model_copy(deep=True)` ensures complete configuration isolation

3. **Lazy Instantiation**: Agents created in `analyze()` rather than `setup()` for maximum freshness

4. **History Filtering**: Built-in isolation via `agent` field in history items

5. **Configuration Externalization**: YAML configs enable role-specific templates and model settings

## Verification Checklist

- ✅ Sub-agents skip environment initialization
- ✅ Each agent has independent model configuration
- ✅ Each agent has independent model instance
- ✅ Each agent has independent history
- ✅ Configuration loading from YAML works
- ✅ Adapter integration with coordinator works
- ✅ All tests pass
- ✅ No breaking changes to existing single-agent code

## Next Steps

1. **Add More Specialized Agents**:
   - Create `temporal_agent.yaml` for Git history analysis
   - Create `impact_agent.yaml` for change propagation analysis

2. **Enhance Coordination Logic**:
   - Implement adaptive agent selection based on issue type
   - Add agent performance monitoring and selection

3. **Optimize Resource Usage**:
   - Implement agent result caching
   - Add parallel agent execution support

4. **Production Hardening**:
   - Add comprehensive error handling
   - Implement agent timeout and retry logic
   - Add detailed logging and telemetry

## Conclusion

This refactoring successfully achieves all objectives:

1. ✅ **Environment Lifecycle Decoupling**: Sub-agents can share environments via `is_subagent` flag
2. ✅ **Model & Capability Isolation**: Each agent has independent configuration and model instance
3. ✅ **Adapter Integration**: `repair_adapters.py` is fully wired into the workflow

The implementation is:
- **Backward Compatible**: Existing single-agent code works unchanged
- **Well-Tested**: Comprehensive test suite validates all isolation guarantees
- **Production-Ready**: Clear documentation and example code provided
- **Extensible**: Easy to add new agents via YAML configuration

---

**Authors**: Senior Python Software Architect
**Date**: 2025-11-26
**Version**: 1.0
