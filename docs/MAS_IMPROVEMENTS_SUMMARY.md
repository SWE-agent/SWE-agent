# Multi-Agent System Improvements Summary

## Overview

This document summarizes the improvements made to the SWE-agent multi-agent system (MARRS) to address three critical issues:

1. Poor agent-coordinator interaction (information loss/redundancy)
2. Agent history not being properly recorded
3. RCA agent inefficiency (too many invalid attempts)

## Issue 1: Agent-Coordinator Interaction

### Problem
The original `_extract_rca_findings()` method only extracted the last 5 thoughts from the trajectory, causing:
- **Information loss**: Critical details like file paths, error messages, and reproduction scripts were missed
- **Information redundancy**: Unstructured text contained duplicate information
- **Poor handoff**: Patch agent received vague, unactionable information

### Solution Implemented
**File**: `sweagent/agent/mas/coordinator.py:274-425`

Implemented a structured handoff document with six clear sections:

1. **PROBLEMATIC FILES**: Lists files identified as containing bugs
2. **ROOT CAUSE**: Explanations of why the bug occurs
3. **ERRORS ENCOUNTERED**: Key error messages and tracebacks
4. **REPRODUCTION**: Information about reproduction scripts
5. **FINAL ANALYSIS**: Agent's conclusions and recommendations
6. **EXIT STATUS**: Completion status

The new extraction logic:
- Parses trajectory steps systematically
- Uses keyword matching to categorize information
- Deduplicates findings
- Formats output in a clear, structured format
- Provides fallback for incomplete analyses

### Why Not LangChain?
LangChain was considered but rejected because:
- Adds unnecessary complexity for this specific use case
- The coordinator pattern is simple and well-defined
- Direct control over handoff format is more important than framework features
- No need for LangChain's memory, chains, or agent abstractions

## Issue 2: Agent History Recording

### Problem
At line 576 in `agents.py`, the `messages` property filters history by `agent["agent"] == self.name`. When agents share an environment via `injected_env`, they write to the same history list but with different names ("rca" vs "patch"), causing:
- **Context confusion**: Agents see each other's messages inappropriately
- **Lost history**: Filtering by name removes relevant context
- **Trajectory corruption**: Mixed agent histories in single trajectory files

### Solution Implemented
**Files**:
- `sweagent/agent/mas/coordinator.py:231-287` (RCA phase)
- `sweagent/agent/mas/coordinator.py:442-510` (Patch phase)

#### Key Changes:

1. **Preserve Agent Histories Separately** (lines 271-280, 496-503):
   ```python
   # Store RCA agent's history in global context
   self.global_context["rca_history"] = rca_agent.history.copy()
   self.global_context["rca_trajectory"] = rca_agent.trajectory.copy()
   ```
   Each agent's complete history is copied to the coordinator's global context before moving to the next phase.

2. **Reset Patch Agent History** (line 468):
   ```python
   patch_agent.history = []
   ```
   The patch agent starts with a clean history to prevent contamination from RCA agent's history.

3. **Independent Trajectory Files**:
   Each agent writes its own trajectory file in separate directories:
   - `/tmp/marrs_output/rca/{request_id}/`
   - `/tmp/marrs_output/patch/{request_id}/`

### Benefits:
- Each agent maintains independent conversation history
- Trajectories are clean and attributable to specific agents
- History can be replayed or analyzed independently
- No cross-contamination between agent contexts

## Issue 3: RCA Agent Efficiency

### Problem
The RCA agent was inefficient due to:
- Using outdated model (gpt-3.5-turbo-0613)
- No systematic exploration strategy in prompts
- Vague instructions leading to random file exploration
- No structured output format
- Low cost limit (2.0) forcing premature termination

### Solution Implemented
**File**: `config/agents/rca_agent.yaml`

#### Key Improvements:

1. **Upgraded Model** (line 109):
   - Changed from: `gpt-3.5-turbo-0613`
   - Changed to: `gpt-4o-mini`
   - Reasoning: More capable at structured reasoning and following complex instructions

2. **Increased Cost Limit** (line 110):
   - Changed from: `2.0`
   - Changed to: `4.0`
   - Allows deeper analysis without premature cutoff

3. **Systematic Investigation Strategy** (lines 19-74):
   Added 6-step structured approach:

   **Step 1: UNDERSTAND THE ISSUE** (2-3 actions)
   - Read issue carefully
   - Identify key symptoms
   - Note relevant clues

   **Step 2: LOCATE RELEVANT CODE** (3-5 actions)
   - Use `find` for file patterns
   - Use `grep` for functions/errors
   - Start specific, broaden if needed

   **Step 3: EXAMINE CODE** (3-5 actions)
   - Read identified files
   - Trace execution flow
   - Look for logical errors

   **Step 4: CREATE REPRODUCTION** (2-3 actions)
   - Write minimal reproduce_issue.py
   - Verify bug exists

   **Step 5: ANALYZE ROOT CAUSE** (1-2 actions)
   - Identify exact problem lines
   - Understand why it fails

   **Step 6: SUBMIT STRUCTURED FINDINGS**
   - Use standardized format

4. **Structured Submission Format** (lines 50-67):
   ```
   FILE: <path>
   FUNCTION/CLASS: <name>
   LINE(S): <numbers>

   ROOT CAUSE: <explanation>
   REPRODUCTION: <script info>
   ERROR OBSERVED: <error message>
   SUGGESTED FIX APPROACH: <high-level fix>
   ```

5. **Efficiency Guidelines** (lines 69-74):
   - Don't randomly explore files
   - If stuck after 5 actions, change strategy
   - Aim for 15-20 total actions
   - Always validate with reproduction script

### Patch Agent Improvements
**File**: `config/agents/patch_agent.yaml`

Also updated patch agent for consistency:
- Upgraded to `gpt-4o-mini` (line 100)
- Added structured implementation strategy (lines 20-59)
- Clear 6-step process from reviewing RCA to submitting patch
- Emphasis on trusting RCA findings (no re-analysis)
- Target: 8-12 actions for implementation

## Summary of Changes

### Files Modified:
1. `sweagent/agent/mas/coordinator.py`:
   - Enhanced `_extract_rca_findings()` with structured parsing
   - Added history preservation in `_run_rca_phase()`
   - Added history reset and preservation in `_run_patch_phase()`

2. `config/agents/rca_agent.yaml`:
   - Upgraded model to gpt-4o-mini
   - Increased cost limit to 4.0
   - Added systematic investigation strategy
   - Added structured submission format
   - Added efficiency guidelines

3. `config/agents/patch_agent.yaml`:
   - Upgraded model to gpt-4o-mini
   - Added structured implementation strategy
   - Improved instructions for using RCA findings
   - Added efficiency guidelines

### Expected Impact:

1. **Better Information Flow**:
   - Structured handoff documents ensure all critical information reaches the patch agent
   - No loss of file paths, error messages, or reproduction details

2. **Clean History Tracking**:
   - Each agent's conversation history is preserved independently
   - Trajectory files are clean and analyzable
   - No cross-contamination between agents

3. **Improved RCA Efficiency**:
   - Systematic approach reduces random exploration
   - Better model improves reasoning quality
   - Structured output format ensures completeness
   - Cost limit increase allows thorough analysis without premature termination
   - Target of 15-20 actions (down from potentially 50+ before)

4. **Faster Overall Execution**:
   - RCA completes faster with focused strategy
   - Patch agent doesn't waste time re-analyzing
   - Total multi-agent workflow should complete in 25-35 actions (down from 60+)

## Testing Recommendations

When testing these improvements:

1. **Test Structured Handoff**:
   - Run on a known issue
   - Check `/tmp/marrs_output/rca/{request_id}/*.traj` for RCA findings
   - Verify all 6 sections are populated in the handoff document
   - Confirm patch agent receives and uses this information

2. **Test History Isolation**:
   - Examine trajectory files for both agents
   - Verify RCA trajectory contains only RCA messages
   - Verify Patch trajectory contains only Patch messages
   - Check that `global_context["rca_history"]` is preserved in coordinator

3. **Test RCA Efficiency**:
   - Count number of actions taken by RCA agent
   - Should be 15-25 actions for typical bugs
   - Check if structured submission format is followed
   - Verify systematic progression through the 6 steps

4. **Integration Test**:
   ```bash
   python tools/run_mas.py \
     --repo <test_repo> \
     --issue_text "Bug description" \
     --output_dir /tmp/test_marrs
   ```
   Compare:
   - Total actions taken (before vs after)
   - Quality of final patch
   - Completeness of RCA report

## Future Enhancements

Potential future improvements not implemented in this round:

1. **Dynamic Strategy Adjustment**:
   - Monitor agent progress
   - Suggest strategy changes if stuck
   - Implement checkpointing for long analyses

2. **Enhanced Coordinator Intelligence**:
   - Validate RCA findings before passing to Patch agent
   - Request additional analysis if findings are incomplete
   - Merge multiple RCA attempts for complex issues

3. **Agent Communication Protocol**:
   - Formalize the handoff document schema
   - Add validation for required fields
   - Support follow-up questions from Patch to RCA

4. **Performance Metrics**:
   - Track success rate by issue type
   - Monitor cost efficiency
   - Measure action efficiency over time
