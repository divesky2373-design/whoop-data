"""CLI interface for the WHOOP Health AI Agent."""

import click

from . import agent, auth, data
from .config import load_settings


@click.group()
def main():
    """WHOOP Health AI Agent - Get personalized health schedules from your WHOOP data."""
    pass


@main.command()
def login():
    """Authenticate with your WHOOP account via OAuth2."""
    settings = load_settings()
    click.echo("Opening browser for WHOOP authorization...")
    click.echo(f"Redirect URI: {settings.redirect_uri}")
    click.echo()

    client = auth.run_auth_flow(settings)
    client.close()

    click.echo()
    click.echo("Authentication successful! Tokens saved.")
    click.echo("You can now run 'whoop-agent schedule' to get your weekly plan.")


@main.command()
@click.option("--days", default=14, help="Number of days of data to analyze (default: 14)")
def schedule(days):
    """Generate a personalized weekly health schedule based on your WHOOP data."""
    settings = load_settings()

    click.echo(f"Fetching your WHOOP data from the last {days} days...")
    client = auth.get_client(settings)

    try:
        health_data = data.fetch_health_data(client, days=days)
    finally:
        client.close()

    click.echo("Analyzing your health data with AI...")
    click.echo()

    result = agent.generate_schedule(settings.anthropic_api_key, health_data)
    click.echo(result)


@main.command()
@click.option("--days", default=14, help="Number of days of data to analyze (default: 14)")
def summary(days):
    """Show a summary of your recent WHOOP health data."""
    settings = load_settings()

    click.echo(f"Fetching your WHOOP data from the last {days} days...")
    client = auth.get_client(settings)

    try:
        health_data = data.fetch_health_data(client, days=days)
    finally:
        client.close()

    click.echo("Generating health summary...")
    click.echo()

    result = agent.generate_summary(settings.anthropic_api_key, health_data)
    click.echo(result)


@main.command()
@click.option("--days", default=14, help="Number of days of data to analyze (default: 14)")
def chat(days):
    """Interactive chat with AI health coach about your WHOOP data."""
    settings = load_settings()

    click.echo(f"Fetching your WHOOP data from the last {days} days...")
    client = auth.get_client(settings)

    try:
        health_data = data.fetch_health_data(client, days=days)
    finally:
        client.close()

    click.echo("Health coach ready! Type 'quit' to exit.")
    click.echo()

    conversation = []

    while True:
        try:
            user_input = click.prompt("You", prompt_suffix="> ")
        except (EOFError, KeyboardInterrupt):
            click.echo("\nGoodbye!")
            break

        if user_input.strip().lower() in ("quit", "exit", "q"):
            click.echo("Goodbye!")
            break

        conversation.append({"role": "user", "content": user_input})

        response = agent.chat(
            settings.anthropic_api_key, health_data, conversation
        )
        conversation.append({"role": "assistant", "content": response})

        click.echo()
        click.echo(f"Coach> {response}")
        click.echo()


if __name__ == "__main__":
    main()
