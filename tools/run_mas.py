"""Entry point for MARRS (Multi-Agent Repository Repair System) with Star Topology.

This script demonstrates the Hub-and-Spoke architecture where:
- The Coordinator (Hub) manages the workflow and shared environment
- Specialized agents (Spokes) only communicate with the Coordinator
- Context flows through the Coordinator (no peer-to-peer communication)

Usage:
    python tools/run_mas.py --repo <github_url> --issue <issue_url>
    python tools/run_mas.py --repo /path/to/local/repo --issue_text "Bug description"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sweagent.agent.mas.coordinator import RepairCoordinator, load_agent_config_from_yaml
from sweagent.environment.repo import GithubRepoConfig, LocalRepoConfig
from sweagent.environment.swe_env import EnvironmentConfig, SWEEnv
from sweagent.utils.log import get_logger

logger = get_logger("run-mas", emoji="🚀")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run MARRS (Multi-Agent Repository Repair System) with Star Topology",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Repository options
    parser.add_argument(
        "--repo",
        required=True,
        help="Repository to analyze (GitHub URL or local path)",
    )

    # Issue options (one required)
    issue_group = parser.add_mutually_exclusive_group(required=True)
    issue_group.add_argument(
        "--issue",
        help="GitHub issue URL (e.g., https://github.com/owner/repo/issues/123)",
    )
    issue_group.add_argument(
        "--issue_text",
        help="Issue description as text",
    )
    issue_group.add_argument(
        "--issue_file",
        type=Path,
        help="Path to file containing issue description",
    )

    # Configuration options
    parser.add_argument(
        "--rca_config",
        type=Path,
        default=Path("config/agents/rca_agent.yaml"),
        help="Path to RCA agent config (default: config/agents/rca_agent.yaml)",
    )
    parser.add_argument(
        "--patch_config",
        type=Path,
        default=Path("config/agents/patch_agent.yaml"),
        help="Path to Patch agent config (default: config/agents/patch_agent.yaml)",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=None,
        help="Output directory (default: auto-generated timestamped dir in trajectories/)",
    )

    # Environment options
    parser.add_argument(
        "--docker_image",
        default="python:3.11",
        help="Docker image to use (default: python:3.11)",
    )

    parser.add_argument(
        "--request_id",
        default="default",
        help="Request identifier for this run (default: 'default')",
    )

    return parser.parse_args()


def get_issue_description(args) -> str:
    """Get issue description from command line arguments."""
    if args.issue:
        # Fetch from GitHub issue URL
        from sweagent.utils.github import _get_problem_statement_from_github_issue, _parse_gh_issue_url

        owner, repo, issue_number = _parse_gh_issue_url(args.issue)
        # This function returns a string directly, not a dict
        issue_description = _get_problem_statement_from_github_issue(owner, repo, issue_number)
        return issue_description

    elif args.issue_text:
        return args.issue_text

    elif args.issue_file:
        return args.issue_file.read_text()

    else:
        raise ValueError("No issue description provided")


def main():
    """Main entry point for MARRS."""
    # Fix Docker permissions if needed (in dev container, permissions can be reset)
    import os
    import subprocess

    docker_socket = "/var/run/docker.sock"
    if os.path.exists(docker_socket):
        try:
            subprocess.run(
                ["sudo", "chmod", "666", docker_socket],
                capture_output=True,
                timeout=5,
            )
        except Exception as e:
            logger.warning(f"Failed to fix Docker permissions: {e}")

    args = parse_args()

    logger.info("=" * 70)
    logger.info("MARRS - Multi-Agent Repository Repair System (Star Topology)")
    logger.info("=" * 70)

    # Get issue description
    logger.info("Loading issue description...")
    issue_description = get_issue_description(args)
    logger.info(f"  Issue preview: {issue_description[:200]}...")

    # Setup environment configuration
    logger.info("\nSetting up environment configuration...")

    # Determine repo config based on input
    if args.repo.startswith("http"):
        repo_config = GithubRepoConfig(github_url=args.repo)
    else:
        repo_config = LocalRepoConfig(path=Path(args.repo))

    env_config = EnvironmentConfig(repo=repo_config)

    # Create shared environment (will be started by first agent)
    logger.info("Creating shared environment...")
    env = SWEEnv.from_config(env_config)
    logger.info(f"  Environment instance: {id(env)}")

    # Load agent configurations
    logger.info("\nLoading agent configurations...")
    rca_config = load_agent_config_from_yaml(args.rca_config)
    logger.info(f"  RCA config loaded: {rca_config.name}")
    patch_config = load_agent_config_from_yaml(args.patch_config)
    logger.info(f"  Patch config loaded: {patch_config.name}")

    # Create coordinator (The Hub)
    logger.info("\nInitializing Star Topology Coordinator...")
    coordinator = RepairCoordinator(
        env=env,
        rca_config=rca_config,
        patch_config=patch_config,
        output_dir=args.output_dir,
    )

    # Run the repair workflow
    logger.info("\n" + "=" * 70)
    logger.info("Starting repair workflow...")
    logger.info("=" * 70 + "\n")

    try:
        final_patch = coordinator.run(
            issue_description=issue_description,
            request_id=args.request_id,
        )

        # Display results
        logger.info("REPAIR WORKFLOW COMPLETED")
        print("FINAL PATCH:")
        print(final_patch)

        return 0

    except Exception as e:
        logger.exception(f"Repair workflow failed: {e}")
        print(f"\nERROR: Repair workflow failed - {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
