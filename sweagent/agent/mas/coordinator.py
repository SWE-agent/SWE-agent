"""Star Topology Multi-Agent Coordinator for MARRS (Multi-Agent Repository Repair System).

This module implements the Hub-and-Spoke architecture where:
- Hub (Coordinator): Central orchestrator that manages the shared environment and workflow
- Spokes (Sub-Agents): Specialized workers (RCA, Patch) that only communicate with the Hub

Key Design Principles:
1. Centralized Control: Coordinator owns the SWEEnv and dispatches tasks
2. No P2P Communication: Agents never communicate with each other directly
3. Context Injection: Coordinator extracts output from Agent A and injects into Agent B's prompt
4. Shared Environment: Single SWEEnv instance shared across all agents
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from sweagent.agent.agents import DefaultAgent, DefaultAgentConfig
from sweagent.agent.problem_statement import TextProblemStatement
from sweagent.environment.swe_env import SWEEnv
from sweagent.types import AgentRunResult
from sweagent.utils.log import get_logger

logger = get_logger("marrs-coordinator", emoji="⭐")


@dataclass
class RepairCoordinatorConfig:
    """Configuration for the RepairCoordinator"""

    rca_agent_config_path: Path
    patch_agent_config_path: Path
    output_dir: Path | None = None  # If None, will use trajectories/ with timestamp


class RepairCoordinator:
    """Star Topology Multi-Agent Coordinator (The Hub).

    Responsibilities:
    1. Environment Management: Initialize and hold the shared SWEEnv instance
    2. Context Management: Extract RCA output and inject into Patch agent's prompt
    3. Task Dispatching: Create and run specialized agents on demand
    4. Result Aggregation: Collect and synthesize final patch

    Workflow:
    1. Initialize shared SWEEnv (once)
    2. Run RCA Agent → extract findings
    3. Process RCA findings (the "Hub Logic")
    4. Run Patch Agent with augmented context
    5. Extract and return final patch
    """

    def __init__(
        self,
        env: SWEEnv,
        rca_config: DefaultAgentConfig,
        patch_config: DefaultAgentConfig,
        output_dir: Path | None = None,
    ):
        """Initialize the Star Topology Coordinator.

        Args:
            env: Shared SWEEnv instance (pre-created but not yet started)
            rca_config: Configuration for RCA (Detective) agent
            patch_config: Configuration for Patch (Developer) agent
            output_dir: Base directory for outputs. If None, creates timestamped dir in trajectories/
        """
        self.env = env
        self.rca_config = rca_config
        self.patch_config = patch_config

        # Create timestamped output directory in trajectories/
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_dir = Path("trajectories") / f"marrs_{timestamp}"
        else:
            self.output_dir = output_dir

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Global context - the Hub's memory
        self.global_context: dict[str, Any] = {}

        logger.info("=" * 60)
        logger.info("RepairCoordinator (Star Topology) initialized")
        logger.info(f"  Shared env: {id(self.env)}")
        logger.info(f"  RCA config: {rca_config.name}")
        logger.info(f"  Patch config: {patch_config.name}")
        logger.info(f"  Output dir: {output_dir}")
        logger.info("=" * 60)

    @classmethod
    def from_config_files(
        cls,
        env: SWEEnv,
        rca_config_path: Path,
        patch_config_path: Path,
        output_dir: Path | None = None,
    ) -> RepairCoordinator:
        """Create coordinator from YAML configuration files.

        Args:
            env: Shared SWEEnv instance
            rca_config_path: Path to RCA agent YAML config
            patch_config_path: Path to Patch agent YAML config
            output_dir: Output directory

        Returns:
            RepairCoordinator instance
        """
        # Load RCA config
        with open(rca_config_path) as f:
            rca_yaml = yaml.safe_load(f)
        rca_config = DefaultAgentConfig(**rca_yaml)

        # Load Patch config
        with open(patch_config_path) as f:
            patch_yaml = yaml.safe_load(f)
        patch_config = DefaultAgentConfig(**patch_yaml)

        return cls(
            env=env,
            rca_config=rca_config,
            patch_config=patch_config,
            output_dir=output_dir,
        )

    def run(self, issue_description: str, request_id: str = "default") -> str:
        """Execute the complete Star Topology repair workflow.

        This is the main orchestration method implementing the Hub-and-Spoke pattern.

        Workflow:
        1. Start shared environment (once)
        2. Spoke 1: Run RCA Agent → extract findings
        3. Hub Logic: Process and store RCA findings
        4. Spoke 2: Run Patch Agent with augmented context
        5. Hub Logic: Extract and return final patch
        6. Close environment

        Args:
            issue_description: The bug report / issue to fix
            request_id: Identifier for this repair request

        Returns:
            Final patch as string
        """
        logger.info("=" * 60)
        logger.info("Starting Star Topology Repair Workflow")
        logger.info(f"  Request ID: {request_id}")
        logger.info("=" * 60)

        try:
            # Start the shared environment and install tools
            # This must be done BEFORE any agent runs, as agents with injected_env
            # skip tool installation and assume the environment is ready
            logger.info(">>> Hub: Initializing shared environment")
            self._initialize_shared_environment()

            # --- Spoke 1: Root Cause Analysis ---
            logger.info("\n>>> Hub: Dispatching RCA Agent (Spoke 1)")
            rca_findings = self._run_rca_phase(issue_description, request_id)

            # --- Hub Logic: Process RCA Output ---
            logger.info("\n>>> Hub: Processing RCA findings")
            self.global_context["rca_report"] = rca_findings
            logger.info(f"  RCA report length: {len(rca_findings)} chars")
            logger.info(f"  RCA report preview: {rca_findings[:200]}...")

            # --- Spoke 2: Patch Generation ---
            logger.info("\n>>> Hub: Dispatching Patch Agent (Spoke 2)")
            final_patch = self._run_patch_phase(issue_description, rca_findings, request_id)

            logger.info("\n>>> Hub: Workflow completed successfully")

            # Save a summary file with all agent histories
            self._save_workflow_summary(request_id)

            return final_patch

        except Exception as e:
            logger.exception(f">>> Hub: Workflow failed: {e}")
            return f"ERROR: Workflow failed - {e}"

        finally:
            # Close environment (if it was started)
            logger.info(">>> Hub: Cleaning up environment")
            try:
                self.env.close()
            except Exception as e:
                logger.warning(f"  Failed to close env: {e}")

    def _initialize_shared_environment(self) -> None:
        """Initialize the shared environment that will be used by all agents.

        This method:
        1. Starts the deployment (Docker container)
        2. Clones/copies the repository
        3. Installs tools from the first agent's config (RCA)
        4. Prepares the environment for agent use

        This is critical because agents with injected_env skip these initialization steps.
        """
        logger.info("  Starting deployment and cloning repository")
        # Start the environment (this initializes deployment and copies repo)
        self.env.start()

        logger.info("  Initializing tools from RCA config")

        # Create a temporary ToolHandler from RCA config to do the installation
        from sweagent.tools.tools import ToolHandler

        tool_handler = ToolHandler(self.rca_config.tools)

        # Install tools for RCA config and also ensure Patch agent's tools
        # are available in the shared environment. When using an injected
        # environment for sub-agents, they skip installation, so the
        # coordinator must install bundles required by all sub-agents.
        logger.info("  Installing tools and bundles for RCA config")
        tool_handler.install(self.env)

        # Also install tools from the patch agent config to ensure any
        # state commands or helper binaries are present for sub-agents.
        try:
            from sweagent.tools.tools import ToolHandler as _ToolHandler

            patch_tool_handler = _ToolHandler(self.patch_config.tools)
            logger.info("  Installing tools and bundles for Patch config")
            patch_tool_handler.install(self.env)
        except Exception:
            # Installing patch tools is best-effort here; log and continue.
            logger.exception("Failed to install Patch agent tools (continuing)")

        logger.info("  ✓ Shared environment initialized and ready")

    def _run_rca_phase(self, issue: str, request_id: str) -> str:
        """Run the Root Cause Analysis phase (Spoke 1).

        The RCA agent analyzes the repository and creates a reproduction script.
        It is FORBIDDEN from submitting patches - analysis only.

        Args:
            issue: Issue description
            request_id: Request identifier

        Returns:
            RCA findings as string (extracted from agent's final thoughts)
        """
        logger.info("--- RCA Phase Start ---")

        # 1. Create RCA agent with injected environment
        logger.info("  Creating RCA agent with injected env")
        rca_agent = DefaultAgent.from_config(self.rca_config, injected_env=self.env)

        # 2. Prepare problem statement
        problem_statement = TextProblemStatement(
            id=f"{request_id}_rca",
            text=issue,
        )

        # 3. Run agent
        agent_output_dir = self.output_dir / "rca" / request_id
        agent_output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("  Running RCA agent...")

        # Store the history before running (in case of shared state issues)
        pre_run_history_length = len(rca_agent.history) if hasattr(rca_agent, "history") else 0

        result = rca_agent.run(
            env=None,  # Agent uses injected_env
            problem_statement=problem_statement,
            output_dir=agent_output_dir,
        )

        # 4. Store RCA agent's history in global context for later reference
        # This preserves the complete conversation history of the RCA agent
        if hasattr(rca_agent, "history"):
            self.global_context["rca_history"] = rca_agent.history.copy()
            logger.info(f"  Preserved RCA agent history ({len(rca_agent.history)} entries)")

        # Store trajectory as well
        if hasattr(rca_agent, "trajectory"):
            self.global_context["rca_trajectory"] = rca_agent.trajectory.copy()
            logger.info(f"  Preserved RCA agent trajectory ({len(rca_agent.trajectory)} steps)")

        # 5. Extract findings (Coordinator Logic)
        logger.info("  Extracting RCA findings from trajectory")
        findings = self._extract_rca_findings(result)

        logger.info(f"--- RCA Phase Complete (findings: {len(findings)} chars) ---")
        return findings

    def _extract_rca_findings(self, result: AgentRunResult) -> str:
        """Extract RCA findings from agent result (Hub Logic).

        This method implements the critical "Handoff Document" extraction with structured format.
        We extract key information including:
        - Identified problematic files
        - Root cause explanation
        - Reproduction steps/script location
        - Error messages and stack traces
        - Suggested fix approach

        Args:
            result: AgentRunResult from RCA agent

        Returns:
            Structured findings string suitable for Patch agent context
        """
        # Initialize structured findings sections
        sections = {
            "files": [],  # Files identified as problematic
            "root_cause": [],  # Root cause explanation
            "reproduction": [],  # Reproduction script info
            "errors": [],  # Error messages
            "commands": [],  # Important commands executed
            "final_analysis": [],  # Final thoughts/conclusions
        }

        # Extract from trajectory with structured analysis
        if result.trajectory:
            # Process trajectory steps to extract structured information
            for step in result.trajectory:
                thought = step.get("thought", "").strip()
                action = step.get("action", "").strip()
                observation = step.get("observation", "").strip()

                # Extract file mentions from thoughts
                if thought:
                    # Look for file references (common patterns)
                    if any(
                        indicator in thought.lower() for indicator in ["file:", "in file", ".py", ".js", ".java", ".go"]
                    ):
                        sections["files"].append(thought)

                    # Look for root cause analysis
                    if any(
                        indicator in thought.lower()
                        for indicator in ["root cause", "because", "issue is", "bug is", "problem is"]
                    ):
                        sections["root_cause"].append(thought)

                    # Look for error analysis
                    if any(indicator in thought.lower() for indicator in ["error", "exception", "traceback", "failed"]):
                        sections["errors"].append(thought)

                # Track important actions
                if action:
                    # Record file operations
                    if action.startswith(("open", "edit", "create", "write")):
                        sections["commands"].append(f"Action: {action[:100]}")

                    # Record reproduction script creation
                    if "reproduce" in action.lower():
                        sections["reproduction"].append(f"Created: {action[:150]}")

                # Extract from observations
                if observation:
                    # Look for error messages in observations
                    if any(indicator in observation.lower() for indicator in ["error:", "traceback", "exception:"]):
                        # Truncate long error messages
                        error_summary = observation[:500] + ("..." if len(observation) > 500 else "")
                        sections["errors"].append(error_summary)

                    # Look for reproduction script output
                    if "reproduce" in observation.lower():
                        sections["reproduction"].append(observation[:300])

            # Get final thoughts (last 3 substantial thoughts)
            final_thoughts = []
            for step in reversed(result.trajectory):
                thought = step.get("thought", "").strip()
                if thought and len(thought) > 20:  # Substantial thoughts only
                    final_thoughts.append(thought)
                if len(final_thoughts) >= 3:
                    break
            sections["final_analysis"] = list(reversed(final_thoughts))

        # Check submission for structured report
        submission = result.info.get("submission", "")
        if submission:
            sections["final_analysis"].insert(0, f"RCA Submission:\n{submission}")

        # Build structured handoff document
        handoff_doc = ["=" * 60, "ROOT CAUSE ANALYSIS REPORT", "=" * 60, ""]

        # Section 1: Identified Files
        if sections["files"]:
            handoff_doc.append("1. PROBLEMATIC FILES:")
            # Deduplicate and format
            unique_files = list(dict.fromkeys(sections["files"][:5]))  # Top 5
            for f in unique_files:
                handoff_doc.append(f"   - {f}")
            handoff_doc.append("")

        # Section 2: Root Cause
        if sections["root_cause"]:
            handoff_doc.append("2. ROOT CAUSE:")
            unique_causes = list(dict.fromkeys(sections["root_cause"][:3]))
            for rc in unique_causes:
                handoff_doc.append(f"   {rc}")
            handoff_doc.append("")

        # Section 3: Errors Encountered
        if sections["errors"]:
            handoff_doc.append("3. ERRORS ENCOUNTERED:")
            for err in sections["errors"][:3]:  # Top 3 errors
                handoff_doc.append(f"   {err}")
                handoff_doc.append("")

        # Section 4: Reproduction
        if sections["reproduction"]:
            handoff_doc.append("4. REPRODUCTION:")
            for rep in sections["reproduction"][:2]:
                handoff_doc.append(f"   {rep}")
            handoff_doc.append("")

        # Section 5: Final Analysis
        if sections["final_analysis"]:
            handoff_doc.append("5. FINAL ANALYSIS:")
            for analysis in sections["final_analysis"]:
                handoff_doc.append(f"   {analysis}")
            handoff_doc.append("")

        # Section 6: Exit Status
        exit_status = result.info.get("exit_status", "")
        if exit_status:
            handoff_doc.append(f"6. EXIT STATUS: {exit_status}")
            handoff_doc.append("")

        handoff_doc.append("=" * 60)

        # If nothing was extracted, provide a fallback
        if len(handoff_doc) <= 5:  # Only header and footer
            handoff_doc = [
                "=" * 60,
                "ROOT CAUSE ANALYSIS REPORT",
                "=" * 60,
                "",
                "WARNING: Limited information extracted from RCA agent.",
                "The RCA agent may not have completed its analysis successfully.",
                "",
                f"Exit Status: {exit_status}",
                "",
                "Patch agent should perform additional investigation if needed.",
                "=" * 60,
            ]

        return "\n".join(handoff_doc)

    def _run_patch_phase(self, issue: str, rca_findings: str, request_id: str) -> str:
        """Run the Patch Generation phase (Spoke 2).

        The Patch agent receives:
        1. Original issue description
        2. RCA findings (injected by Coordinator)

        This is the key "Context Injection" step that defines the Hub-and-Spoke model.

        Args:
            issue: Original issue description
            rca_findings: Findings from RCA agent (processed by Hub)
            request_id: Request identifier

        Returns:
            Final patch as string
        """
        logger.info("--- Patch Phase Start ---")

        # 1. Create Patch agent with injected environment
        logger.info("  Creating Patch agent with injected env")
        patch_agent = DefaultAgent.from_config(self.patch_config, injected_env=self.env)

        # CRITICAL FIX: Ensure patch agent starts with a clean history
        # The issue was that agents were sharing history when using injected_env
        # Each agent needs its own independent history to avoid confusion
        patch_agent.history = []
        logger.info("  Reset Patch agent history to ensure independence from RCA agent")

        # 2. Construct Augmented Prompt (CRITICAL HUB LOGIC)
        # This is where the Coordinator explicitly injects RCA findings
        logger.info("  Augmenting problem statement with RCA findings")
        augmented_task = self._build_augmented_prompt(issue, rca_findings)

        # 3. Prepare problem statement
        problem_statement = TextProblemStatement(
            id=f"{request_id}_patch",
            text=augmented_task,
            extra_fields={
                "rca_findings": rca_findings,  # Also pass as template variable
            },
        )

        # 4. Run agent
        agent_output_dir = self.output_dir / "patch" / request_id
        agent_output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("  Running Patch agent...")
        result = patch_agent.run(
            env=None,  # Agent uses injected_env
            problem_statement=problem_statement,
            output_dir=agent_output_dir,
        )

        # 5. Store Patch agent's history in global context
        if hasattr(patch_agent, "history"):
            self.global_context["patch_history"] = patch_agent.history.copy()
            logger.info(f"  Preserved Patch agent history ({len(patch_agent.history)} entries)")

        if hasattr(patch_agent, "trajectory"):
            self.global_context["patch_trajectory"] = patch_agent.trajectory.copy()
            logger.info(f"  Preserved Patch agent trajectory ({len(patch_agent.trajectory)} steps)")

        # 6. Extract patch (Coordinator Logic)
        logger.info("  Extracting patch from result")
        patch = self._extract_patch(result)

        logger.info(f"--- Patch Phase Complete (patch: {len(patch)} chars) ---")
        return patch

    def _build_augmented_prompt(self, issue: str, rca_findings: str) -> str:
        """Build the augmented prompt for Patch agent (Hub Logic).

        This method demonstrates the Coordinator's role in synthesizing context.
        The Patch agent receives a carefully constructed prompt that includes:
        1. Original issue
        2. Processed RCA findings
        3. Clear instructions

        Args:
            issue: Original issue description
            rca_findings: Processed RCA findings

        Returns:
            Augmented task string
        """
        # Use the template from patch_agent config if it has placeholders
        # Otherwise construct manually
        template = """
TASK: Fix the following issue in the repository.

ISSUE DESCRIPTION:
{issue}

ROOT CAUSE ANALYSIS (from RCA Agent):
{rca_findings}

INSTRUCTIONS:
1. The RCA Agent has already analyzed the issue and identified the root cause above
2. A reproduction script (reproduce_issue.py) may already exist in the repository
3. Focus on IMPLEMENTING the fix based on the RCA guidance
4. If reproduce_issue.py exists, run it to verify your fix works
5. Once the fix is complete and verified, use the 'submit' command to submit your patch

IMPORTANT:
- Trust the RCA analysis - it has already identified the problematic code
- Do NOT re-analyze from scratch - use the RCA findings to guide your fix
- The shared environment already has all necessary setup from the RCA phase
"""

        return template.format(issue=issue, rca_findings=rca_findings)

    def _extract_patch(self, result: AgentRunResult) -> str:
        """Extract the final patch from Patch agent result (Hub Logic).

        Args:
            result: AgentRunResult from Patch agent

        Returns:
            Patch as string
        """
        # Check if agent submitted
        exit_status = result.info.get("exit_status", "")
        submission = result.info.get("submission", "")

        if submission:
            logger.info("  Patch agent submitted a patch")
            return submission

        # Fallback: try to get diff from trajectory
        logger.info("  No submission found, attempting to extract from trajectory")
        if result.trajectory:
            for step in reversed(result.trajectory):
                observation = step.get("observation", "")
                if "diff" in observation.lower() or "patch" in observation.lower():
                    return observation

        # Final fallback
        return f"Patch agent completed with status: {exit_status}\nNo explicit patch found in submission."

    def _save_workflow_summary(self, request_id: str) -> None:
        """Save a comprehensive workflow summary with all agent histories.

        This creates a JSON file containing:
        - Metadata about the run
        - Complete RCA agent history and trajectory
        - Complete Patch agent history and trajectory
        - Structured RCA findings
        - Final patch

        Args:
            request_id: Request identifier for this run
        """
        import json

        summary_path = self.output_dir / f"workflow_summary_{request_id}.json"

        summary = {
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "output_directory": str(self.output_dir),
            "agents": {
                "rca": {
                    "name": self.rca_config.name,
                    "role": self.rca_config.role if hasattr(self.rca_config, "role") else "rca",
                    "model": self.rca_config.model.name
                    if hasattr(self.rca_config.model, "name")
                    else str(self.rca_config.model),
                    "history_entries": len(self.global_context.get("rca_history", [])),
                    "trajectory_steps": len(self.global_context.get("rca_trajectory", [])),
                    "trajectory_file": f"rca/{request_id}/{request_id}_rca.traj",
                },
                "patch": {
                    "name": self.patch_config.name,
                    "role": self.patch_config.role if hasattr(self.patch_config, "role") else "patch",
                    "model": self.patch_config.model.name
                    if hasattr(self.patch_config.model, "name")
                    else str(self.patch_config.model),
                    "history_entries": len(self.global_context.get("patch_history", [])),
                    "trajectory_steps": len(self.global_context.get("patch_trajectory", [])),
                    "trajectory_file": f"patch/{request_id}/{request_id}_patch.traj",
                },
            },
            "rca_findings_summary": self.global_context.get("rca_report", "No findings recorded")[:500],
            "histories": {
                "rca_history": self.global_context.get("rca_history", []),
                "patch_history": self.global_context.get("patch_history", []),
            },
        }

        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2, default=str)

        logger.info(f"  Saved workflow summary to: {summary_path}")

        # Also save a human-readable text summary
        text_summary_path = self.output_dir / f"workflow_summary_{request_id}.txt"
        with open(text_summary_path, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("MARRS WORKFLOW SUMMARY\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Request ID: {request_id}\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Output Directory: {self.output_dir}\n\n")

            f.write("-" * 80 + "\n")
            f.write("RCA AGENT\n")
            f.write("-" * 80 + "\n")
            f.write(f"Model: {summary['agents']['rca']['model']}\n")
            f.write(f"History Entries: {summary['agents']['rca']['history_entries']}\n")
            f.write(f"Trajectory Steps: {summary['agents']['rca']['trajectory_steps']}\n")
            f.write(f"Trajectory File: {summary['agents']['rca']['trajectory_file']}\n\n")

            f.write("-" * 80 + "\n")
            f.write("PATCH AGENT\n")
            f.write("-" * 80 + "\n")
            f.write(f"Model: {summary['agents']['patch']['model']}\n")
            f.write(f"History Entries: {summary['agents']['patch']['history_entries']}\n")
            f.write(f"Trajectory Steps: {summary['agents']['patch']['trajectory_steps']}\n")
            f.write(f"Trajectory File: {summary['agents']['patch']['trajectory_file']}\n\n")

            f.write("-" * 80 + "\n")
            f.write("RCA FINDINGS (Preview)\n")
            f.write("-" * 80 + "\n")
            f.write(self.global_context.get("rca_report", "No findings recorded"))
            f.write("\n\n")

            f.write("=" * 80 + "\n")
            f.write(f"Complete histories available in: {summary_path}\n")
            f.write("=" * 80 + "\n")

        logger.info(f"  Saved text summary to: {text_summary_path}")


def load_agent_config_from_yaml(config_path: Path) -> DefaultAgentConfig:
    """Load a DefaultAgentConfig from a YAML file.

    Args:
        config_path: Path to YAML config file

    Returns:
        DefaultAgentConfig instance
    """
    with open(config_path) as f:
        yaml_data = yaml.safe_load(f)

    # Handle nested 'agent' key if present
    if "agent" in yaml_data:
        yaml_data = yaml_data["agent"]

    return DefaultAgentConfig(**yaml_data)
