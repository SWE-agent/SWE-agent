"""GitHub integration CLI commands for SWE-agent.

This module provides CLI commands for running SWE-agent as a GitHub Action
or bot, supporting both modes through a unified interface.
"""

from pathlib import Path

import click
import yaml

from sweagent.agent.agents import Agent
from sweagent.github.action import GitHubActionRouter
from sweagent.github.bot import GitHubBotRouter


def load_config(config_path: str = None) -> dict:
    """Load GitHub integration configuration.

    Args:
        config_path: Optional path to config file

    Returns:
        dict: Configuration dictionary
    """
    if not config_path:
        config_path = Path(__file__).parent.parent.parent / "config" / "github.yaml"

    with open(config_path) as f:
        return yaml.safe_load(f)


@click.group()
def github():
    """GitHub integration commands."""
    pass


@github.command()
@click.option("--event-path", type=click.Path(exists=True), required=True, help="Path to GitHub event payload JSON")
@click.option("--token", envvar="GITHUB_TOKEN", required=True, help="GitHub API token")
@click.option("--config", type=click.Path(exists=True), help="Path to config file")
def action(event_path: str, token: str, config: str = None):
    """Run as GitHub Action.

    Process GitHub events from Actions environment using the provided
    event payload and token.
    """
    # Initialize agent
    agent = Agent()

    # Create router
    router = GitHubActionRouter(agent=agent, event_path=Path(event_path), token=token)

    try:
        # Handle event
        router.handle_event()
    except Exception as e:
        click.echo(f"Error processing event: {e}", err=True)
        raise click.Abort()


@github.command()
@click.option("--port", type=int, default=8000, help="Webhook server port")
@click.option("--token", envvar="GITHUB_TOKEN", required=True, help="GitHub API token")
@click.option("--webhook-secret", envvar="GITHUB_WEBHOOK_SECRET", required=True, help="GitHub webhook secret")
@click.option("--config", type=click.Path(exists=True), help="Path to config file")
def bot(port: int, token: str, webhook_secret: str, config: str = None):
    """Run as GitHub bot.

    Start webhook server to process GitHub events in bot mode.
    """
    # Load config
    config_data = load_config(config)
    bot_config = config_data["github"]["bot"]

    # Use config port if not overridden
    if port == 8000:
        port = bot_config["webhook"]["port"]

    # Initialize agent
    agent = Agent()

    # Create router
    router = GitHubBotRouter(agent=agent, webhook_port=port, webhook_secret=webhook_secret, token=token)

    try:
        # Start webhook server
        router.start()
        click.echo(f"GitHub bot webhook server running on port {port}")

        # Keep main thread alive
        try:
            while True:
                click.pause()
        except KeyboardInterrupt:
            click.echo("Stopping webhook server...")
            router.stop()
    except Exception as e:
        click.echo(f"Error running bot: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    github()
