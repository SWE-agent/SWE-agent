# Multi-Agent System Architecture Documentation

## System Architecture Overview

This document provides detailed architectural diagrams and explanations for the multi-agent repair system.

---

## 1. Star Topology Architecture

### High-Level View

```
┌────────────────────────────────────────────────────────────────┐
│                     USER / EXTERNAL SYSTEM                     │
│                                                                │
│  Submits: RepairRequest                                        │
│  Receives: Final RepairPatch + Trajectory                      │
└──────────────────────┬─────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────────┐
│                    REPAIR COORDINATOR                          │
│                    (Central Hub - Star Center)                 │
│                                                                │
│  Responsibilities:                                             │
│  • Dispatch RepairRequests to agents (context=None)           │
│  • Store results privately in _coordinator_evidence           │
│  • Aggregate evidence for patch generation                    │
│  • Synthesize final patch with contract validation            │
│                                                                │
│  Private Data (inaccessible to sub-agents):                   │
│  • _coordinator_evidence: {                                   │
│      "topology": AgentResult(...),                            │
│      "temporal": AgentResult(...),                            │
│      "impact": AgentResult(...),                              │
│      "contract": AgentResult(...)                             │
│    }                                                           │
└──┬─────────┬─────────┬─────────┬─────────────────────────────┘
   │         │         │         │
   │ (1)     │ (2)     │ (3)     │ (4)
   │         │         │         │
   ▼         ▼         ▼         ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
│Topology│ │Temporal│ │ Impact │ │ Contract │
│ Agent  │ │ Agent  │ │ Agent  │ │  Agent   │
└────────┘ └────────┘ └────────┘ └──────────┘

ISOLATION RULES (Enforced):
• Sub-agents receive: RepairRequest + context=None
• Sub-agents return: AgentResult
• Sub-agents CANNOT access: _coordinator_evidence
• Sub-agents CANNOT communicate with each other
```

---

## 2. Component Interaction Flow

### Sequential Execution Model

```
┌──────────────────────────────────────────────────────────────┐
│ PHASE 1: Isolated Analysis (Parallel-Ready)                 │
└──────────────────────────────────────────────────────────────┘

  Coordinator                TopologyAgent
      │                           │
      ├──RepairRequest────────────▶│
      │  (context=None)            │
      │                           │ Analyze dependency graph
      │◀────AgentResult────────────┤
      │  (evidence, artifacts)     │
      │
      │  [Store privately in
      │   _coordinator_evidence]
      │
      │                      TemporalAgent
      │                           │
      ├──RepairRequest────────────▶│
      │  (context=None)            │
      │                           │ Analyze git history
      │◀────AgentResult────────────┤
      │  (evidence, artifacts)     │
      │
      │  [Store privately]
      │
      │                      ImpactAgent
      │                           │
      ├──RepairRequest────────────▶│
      │  (context=None)            │
      │                           │ Trace change propagation
      │◀────AgentResult────────────┤
      │  (evidence, artifacts)     │
      │
      │  [Store privately]
      │

┌──────────────────────────────────────────────────────────────┐
│ PHASE 2: Patch Generation (Coordinator Private)             │
└──────────────────────────────────────────────────────────────┘

  Coordinator              PatchGenerator
      │                           │
      │  [Aggregate all evidence  │
      │   from _coordinator_      │
      │   evidence dict]          │
      │                           │
      ├──generate(request,        │
      │            evidence)───────▶│
      │                           │ Create patch using
      │                           │ aggregated evidence
      │◀────RepairPatch────────────┤
      │  (diff, rationale)         │

┌──────────────────────────────────────────────────────────────┐
│ PHASE 3: Contract Validation                                │
└──────────────────────────────────────────────────────────────┘

  Coordinator              ContractAgent
      │                           │
      │  [Create specialized      │
      │   RepairRequest with      │
      │   patch in context_files] │
      │                           │
      ├──RepairRequest────────────▶│
      │  (context_files=          │
      │   {"patch.diff": ...})    │
      │  (context=None)            │
      │                           │ Validate patch
      │◀────AgentResult────────────┤
      │  (score, evidence)         │
      │
      │  [Synthesize final patch
      │   with contract results]
      │
      ▼
  Final RepairPatch
  (validated, risk_score)
```

---

## 3. Data Structure Flow

### RepairRequest → AgentResult → RepairPatch

```
┌─────────────────────────────────────────────────────────────┐
│ INPUT: RepairRequest                                        │
├─────────────────────────────────────────────────────────────┤
│ • id: str                                                   │
│ • repository: str                                           │
│ • target_commit: str                                        │
│ • failing_tests: list[str]                                  │
│ • context_files: dict[str, str]  ← Coordinator injects     │
│ • metadata: dict                                            │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
        ┌─────────────────────────┐
        │    Agent.analyze()      │
        │    (isolated)           │
        └─────────────┬───────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ OUTPUT: AgentResult                                         │
├─────────────────────────────────────────────────────────────┤
│ • role: str                    ← Agent identity            │
│ • evidence: list[str]          ← Human-readable findings   │
│ • artifacts: dict[str, Any]    ← Structured data           │
│ • score: float (0.0-1.0)       ← Confidence/quality        │
│ • metadata: dict               ← Additional context        │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ (Multiple AgentResults)
                      │
                      ▼
        ┌─────────────────────────┐
        │  Coordinator Aggregates │
        │  (private)              │
        └─────────────┬───────────┘
                      │
                      ▼
        ┌─────────────────────────┐
        │  PatchGenerator.        │
        │  generate()             │
        └─────────────┬───────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ OUTPUT: RepairPatch                                         │
├─────────────────────────────────────────────────────────────┤
│ • diff: str                    ← Unified diff format       │
│ • files_changed: list[str]     ← List of modified files    │
│ • rationale: str               ← Explanation               │
│ • risk_score: float            ← Estimated risk (0.0-1.0)  │
│ • validated: bool              ← Contract validation flag  │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Integration with swe-agent

### SWEAgentAdapter Bridge

```
┌─────────────────────────────────────────────────────────────┐
│ Repair Framework (New)                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  BaseAgent (abstract)                                       │
│    ↑                                                        │
│    │ extends                                                │
│    │                                                        │
│  SWEAgentAdapter  ←──────┐                                 │
│    │                      │                                 │
│    │ wraps               │ converts                        │
│    ▼                      │                                 │
│  DefaultAgent ───────────┘                                 │
│    │                                                        │
│    │ uses                                                   │
│    ▼                                                        │
├─────────────────────────────────────────────────────────────┤
│ SWE-Agent Core (Existing)                                   │
├─────────────────────────────────────────────────────────────┤
│  • SWEEnv (shared environment)                              │
│  • ToolHandler (command execution)                          │
│  • HistoryProcessor (context filtering)                     │
│  • AbstractModel (LLM interface)                            │
│  • Hooks (lifecycle events)                                 │
└─────────────────────────────────────────────────────────────┘

Key Points:
• SWEAgentAdapter implements BaseAgent.analyze()
• Internally uses DefaultAgent.run() for execution
• Converts RepairRequest → ProblemStatement
• Converts Trajectory → AgentResult
• Leverages existing swe-agent infrastructure
```

### History Isolation Mechanism

```
┌─────────────────────────────────────────────────────────────┐
│ Shared History (in SWEEnv)                                  │
├─────────────────────────────────────────────────────────────┤
│ [                                                           │
│   {"role": "system", "content": "...", "agent": "topology"},│
│   {"role": "user", "content": "...", "agent": "topology"},  │
│   {"role": "assistant", "content": "...", "agent": "topology"},│
│   {"role": "system", "content": "...", "agent": "temporal"},│
│   {"role": "user", "content": "...", "agent": "temporal"},  │
│   {"role": "assistant", "content": "...", "agent": "temporal"},│
│   ...                                                       │
│ ]                                                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ Filter by agent name
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
TopologyAgent.messages      TemporalAgent.messages
[only "topology" items]     [only "temporal" items]

Isolation Guarantee:
• Each agent's messages property filters history by agent field
• Agents only see their own conversation thread
• No access to other agents' interactions
```

---

## 5. Hook System Integration

### OrchestratorHook Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Coordinator's Hook Usage                                    │
└─────────────────────────────────────────────────────────────┘

  Coordinator            OrchestratorHook         Agent
      │                         │                   │
      ├──set_current_agent──────▶│                  │
      │  ("topology")            │                  │
      │                         │                  │
      ├──run_agent──────────────┼──────────────────▶│
      │                         │                  │
      │                         │◀─on_run_start────┤
      │                         │  (hook callback)  │
      │                         │                  │
      │                         │◀─on_step_done────┤
      │                         │  (hook callback)  │
      │                         │                  │
      │                         │◀─on_run_done─────┤
      │                         │  (trajectory,     │
      │                         │   info)           │
      │                         │                  │
      │                         │  [Store in hook]  │
      │                         │                  │
      │◀──get_result─────────────┤                  │
      │  (trajectory, info)      │                  │
      │                         │                  │
      │  [Convert to            │                  │
      │   AgentResult]          │                  │
      │                         │                  │
      ├──clear_current_result───▶│                  │
      │                         │                  │

Key: Hook provides ONE-WAY telemetry (agent → coordinator)
```

---

## 6. Deployment Scenarios

### Scenario 1: Local Testing (Mock Agents)

```
User
  │
  ├─ python tools/multi_agent_demo.py
  │
  ▼
RepairCoordinator
  │
  ├─ MockTopologyAgent (in-process)
  ├─ MockTemporalAgent (in-process)
  ├─ MockImpactAgent (in-process)
  └─ MockContractAgent (in-process)

Characteristics:
• Fast execution (no LLM calls)
• Deterministic results
• Good for testing coordination logic
```

### Scenario 2: Local with SWEAgentAdapter (Real Analysis)

```
User
  │
  ├─ python my_repair_script.py
  │
  ▼
RepairCoordinator
  │
  ├─ SWEAgentAdapter(TopologyAgent)
  │     └─ DefaultAgent + SWEEnv (shared)
  │
  ├─ SWEAgentAdapter(TemporalAgent)
  │     └─ DefaultAgent + SWEEnv (shared)
  │
  ├─ SWEAgentAdapter(ImpactAgent)
  │     └─ DefaultAgent + SWEEnv (shared)
  │
  └─ SWEAgentAdapter(ContractAgent)
        └─ DefaultAgent + SWEEnv (shared)

Characteristics:
• Real LLM-based analysis
• Shared environment for efficiency
• Isolated agent histories
```

### Scenario 3: Distributed (Future)

```
User
  │
  ├─ HTTP API Request
  │
  ▼
RepairCoordinator (Server)
  │
  ├─ gRPC/REST → TopologyAgent Service
  │               (separate process/container)
  │
  ├─ gRPC/REST → TemporalAgent Service
  │               (separate process/container)
  │
  ├─ gRPC/REST → ImpactAgent Service
  │               (separate process/container)
  │
  └─ gRPC/REST → ContractAgent Service
                  (separate process/container)

Characteristics:
• Horizontal scalability
• Language-agnostic agents
• Network-level isolation
```

---

## 7. Security & Safety Boundaries

### Isolation Enforcement Layers

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Code-Level Enforcement                            │
├─────────────────────────────────────────────────────────────┤
│ • RepairCoordinator.run() hardcodes context=None           │
│ • _coordinator_evidence is private (name mangling)         │
│ • BaseAgent.analyze() signature requires context param     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Runtime Assertions                                 │
├─────────────────────────────────────────────────────────────┤
│ • Demo agents assert context is None                       │
│ • Integration tests verify isolation                       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Documentation & Convention                         │
├─────────────────────────────────────────────────────────────┤
│ • Docstrings warn against passing context                  │
│ • Quick start guide explains isolation rules               │
│ • Architecture docs mandate star topology                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Environment-Level Isolation (swe-agent)            │
├─────────────────────────────────────────────────────────────┤
│ • History filtered by agent field                          │
│ • Tool blocklists prevent dangerous operations             │
│ • Cost limits per agent                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Cost & Performance Considerations

### Token Usage Strategy

```
┌─────────────────────────────────────────────────────────────┐
│ Agent-Level Cost Control                                    │
├─────────────────────────────────────────────────────────────┤
│ TopologyAgent:     per_instance_cost_limit = 1.0 USD       │
│ TemporalAgent:     per_instance_cost_limit = 1.0 USD       │
│ ImpactAgent:       per_instance_cost_limit = 1.0 USD       │
│ ContractAgent:     per_instance_cost_limit = 1.5 USD       │
│                                           (needs to run     │
│                                            tests)           │
├─────────────────────────────────────────────────────────────┤
│ TOTAL BUDGET:      ~4.5 USD per repair attempt             │
└─────────────────────────────────────────────────────────────┘

Optimizations:
• History filtering reduces context size
• Isolated agents can run in parallel (future)
• Coordinator aggregates efficiently without LLM calls
```

---

## Summary

This architecture achieves:

✅ **Strict Isolation**: Sub-agents cannot access peer data
✅ **Clear Responsibility**: Coordinator owns all aggregation logic
✅ **Minimal Invasion**: Leverages existing swe-agent infrastructure
✅ **Extensibility**: Easy to add new agent types
✅ **Testability**: Each component can be tested independently
✅ **Scalability**: Star topology enables parallel execution (future)

The star topology ensures that all communication flows through the coordinator, making the system predictable, debuggable, and maintainable.
