import argparse
import json
from pathlib import Path

def analyze_trajectories(directory_path: Path) -> dict:
    total_cost = 0.0
    total_api_calls = 0
    total_tokens_sent = 0
    total_tokens_received = 0
    exit_statuses = {}

    # Find all *.traj files under the directory_path recursively
    traj_files = list(directory_path.rglob("*.traj"))
    for traj_file in traj_files:
        try:
            data = json.loads(traj_file.read_text())
            info = data.get("info", {})
            model_stats = info.get("model_stats", {})
            
            # total costs
            total_cost += model_stats.get("instance_cost", 0.0)
            
            # total API calls
            total_api_calls += model_stats.get("api_calls", 0)
            
            # token usage (sum of sent and received)
            total_tokens_sent += model_stats.get("tokens_sent", 0)
            total_tokens_received += model_stats.get("tokens_received", 0)
            
            # exit status distribution
            exit_status = info.get("exit_status", "unknown")
            exit_statuses[exit_status] = exit_statuses.get(exit_status, 0) + 1
        except Exception:
            # Skip invalid files or handle error
            pass
            
    total_tokens = total_tokens_sent + total_tokens_received
    
    return {
        "total_cost": total_cost,
        "total_api_calls": total_api_calls,
        "tokens_sent": total_tokens_sent,
        "tokens_received": total_tokens_received,
        "total_tokens": total_tokens,
        "exit_status_distribution": exit_statuses,
    }

def main(args: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Analyze trajectory JSON files and compile metrics.")
    parser.add_argument(
        "-d", "--directory",
        type=Path,
        required=True,
        help="Directory to search for .traj files recursively"
    )
    parser.add_argument(
        "--output-markdown",
        type=Path,
        help="Path to save the Markdown report summary"
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Path to save the JSON metrics"
    )
    
    parsed_args = parser.parse_args(args)
    metrics = analyze_trajectories(parsed_args.directory)
    
    if parsed_args.output_json:
        parsed_args.output_json.write_text(json.dumps(metrics, indent=2))
        
    if parsed_args.output_markdown:
        # Generate Markdown content
        md_lines = [
            "# Trajectory Analysis Summary Report",
            "",
            f"**Total Cost (USD)**: ${metrics['total_cost']:.4f}",
            f"**Total API Calls**: {metrics['total_api_calls']}",
            f"**Total Tokens (Sent + Received)**: {metrics['total_tokens']} (Sent: {metrics['tokens_sent']}, Received: {metrics['tokens_received']})",
            "",
            "## Exit Status Distribution",
            "",
        ]
        for status, count in metrics['exit_status_distribution'].items():
            md_lines.append(f"- **{status}**: {count}")
        parsed_args.output_markdown.write_text("\n".join(md_lines))

if __name__ == "__main__":
    main()
