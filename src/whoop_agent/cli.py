"""CLI interface for the WHOOP Health AI Agent."""

import click

from . import agent, auth, data, volume_data, volume_store, volume_chart
from .config import load_settings, load_volume_settings


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


@main.group()
def volume():
    """Monitor AI agent token trading volumes."""
    pass


@volume.command()
@click.option("--limit", default=15, help="Number of tokens to fetch (default: 15)")
def fetch(limit):
    """Fetch today's AI agent token volumes and save locally."""
    vs = load_volume_settings()

    click.echo("Fetching AI agent token volumes from CoinGecko...")
    snapshot = volume_data.fetch_daily_snapshot(
        api_key=vs.coingecko_api_key, limit=limit
    )

    conn = volume_store.init_db(vs.volume_db_path)
    try:
        volume_store.save_snapshot(conn, snapshot)
    finally:
        conn.close()

    click.echo(f"Saved {len(snapshot['tokens'])} tokens for {snapshot['date']}")
    click.echo()

    # Print summary table
    click.echo(f"{'Symbol':<10} {'Name':<25} {'24h Volume':>15} {'Price':>12} {'24h %':>8}")
    click.echo("-" * 72)
    for t in sorted(snapshot["tokens"], key=lambda x: x["volume_usd"], reverse=True):
        price = f"${t['price_usd']:,.2f}" if t.get("price_usd") else "N/A"
        pct = f"{t['price_change_24h_pct']:+.1f}%" if t.get("price_change_24h_pct") is not None else "N/A"
        vol = f"${t['volume_usd']:,.0f}"
        click.echo(f"{t['symbol']:<10} {t['name']:<25} {vol:>15} {price:>12} {pct:>8}")


@volume.command()
def changes():
    """Show daily volume changes compared to previous fetch."""
    vs = load_volume_settings()
    conn = volume_store.init_db(vs.volume_db_path)

    try:
        diffs = volume_store.get_daily_changes(conn)
    finally:
        conn.close()

    if not diffs:
        click.echo("Need at least 2 days of data. Run 'volume fetch' again tomorrow.")
        return

    click.echo(f"{'Symbol':<10} {'Name':<20} {'Today Vol':>15} {'Yest Vol':>15} {'Change':>10}")
    click.echo("-" * 72)
    for d in diffs:
        tv = f"${d['today_volume']:,.0f}"
        yv = f"${d['yesterday_volume']:,.0f}" if d["yesterday_volume"] else "N/A"
        pct = f"{d['change_pct']:+.1f}%" if d["change_pct"] is not None else "NEW"
        click.echo(f"{d['symbol']:<10} {d['name']:<20} {tv:>15} {yv:>15} {pct:>10}")


@volume.command()
@click.option("--days", default=30, help="Number of days of history (default: 30)")
def chart(days):
    """Generate volume visualization charts from stored data."""
    vs = load_volume_settings()
    conn = volume_store.init_db(vs.volume_db_path)

    try:
        snapshots = volume_store.get_snapshots(conn, days=days)
    finally:
        conn.close()

    if not snapshots:
        click.echo("No data yet. Run 'volume fetch' first.")
        return

    output_dir = vs.chart_output_dir
    generated = []

    # Latest snapshot bar chart
    path = volume_chart.chart_top_volumes(snapshots[-1], output_dir)
    generated.append(path)

    # Aggregate volume trend (needs 2+ snapshots)
    if len(snapshots) >= 2:
        path = volume_chart.chart_aggregate_volume(snapshots, output_dir)
        if path:
            generated.append(path)

    # Daily changes chart (needs 2+ snapshots)
    if len(snapshots) >= 2:
        conn = volume_store.init_db(vs.volume_db_path)
        try:
            diffs = volume_store.get_daily_changes(conn)
        finally:
            conn.close()
        if diffs:
            path = volume_chart.chart_daily_changes(diffs, output_dir)
            if path:
                generated.append(path)

    click.echo(f"Generated {len(generated)} chart(s):")
    for p in generated:
        click.echo(f"  {p}")


@volume.command()
@click.option("--token", required=True, help="CoinGecko coin ID (e.g. fetch-ai)")
@click.option("--days", default=30, help="Days of history (default: 30)")
def track(token, days):
    """Track and chart a specific token's volume history."""
    vs = load_volume_settings()

    click.echo(f"Fetching {days}-day volume history for '{token}'...")
    client = volume_data.CoinGeckoClient(api_key=vs.coingecko_api_key)
    history = client.fetch_token_volume_history(token, days=days)

    if not history:
        click.echo(f"No data found for '{token}'. Check the CoinGecko coin ID.")
        return

    path = volume_chart.chart_volume_trend(history, token, vs.chart_output_dir)
    click.echo(f"Chart saved: {path}")


@volume.command(name="list")
def list_tokens():
    """List all tracked AI agent tokens from local database."""
    vs = load_volume_settings()
    conn = volume_store.init_db(vs.volume_db_path)

    try:
        tokens = volume_store.list_tracked_tokens(conn)
    finally:
        conn.close()

    if not tokens:
        click.echo("No tokens tracked yet. Run 'volume fetch' first.")
        return

    click.echo(f"{'Symbol':<10} {'Coin ID':<30} {'Name'}")
    click.echo("-" * 60)
    for t in tokens:
        click.echo(f"{t['symbol']:<10} {t['coin_id']:<30} {t['name']}")


if __name__ == "__main__":
    main()
