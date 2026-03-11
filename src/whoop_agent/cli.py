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


# ---------------------------------------------------------------------------
# Agent-to-Agent Volume Monitor
# ---------------------------------------------------------------------------

@main.group()
def volume():
    """Monitor agent-to-agent transaction volumes on-chain."""
    pass


@volume.command()
@click.option("--days", default=30, help="Days of data to fetch (default: 30)")
@click.option("--source", type=click.Choice(["dune", "basescan", "demo", "auto"]),
              default="auto", help="Data source (default: auto)")
def fetch(days, source):
    """Fetch agent-to-agent transaction volumes from on-chain data.

    Sources:
      dune     — x402 protocol data via Dune Analytics (needs DUNE_API_KEY)
      basescan — USDC transfers between ERC-8004 agents on Base (needs BASESCAN_API_KEY)
      demo     — realistic demo data based on public x402 metrics
      auto     — tries dune, then basescan, then demo
    """
    vs = load_volume_settings()
    conn = volume_store.init_db(vs.volume_db_path)

    try:
        if source == "auto":
            if vs.dune_api_key:
                source = "dune"
            elif vs.basescan_api_key:
                source = "basescan"
            else:
                source = "demo"

        if source == "dune":
            if not vs.dune_api_key:
                raise click.ClickException(
                    "DUNE_API_KEY required. Get one at https://dune.com/settings/api"
                )
            click.echo(f"Fetching x402 agent transaction data from Dune ({days} days)...")
            volumes = volume_data.fetch_agent_volume_dune(vs.dune_api_key, days=days)
            saved = volume_store.save_daily_volumes(conn, volumes, source="dune")
            click.echo(f"Saved {saved} daily records from Dune.")

        elif source == "basescan":
            if not vs.basescan_api_key:
                raise click.ClickException(
                    "BASESCAN_API_KEY required (Etherscan V2). "
                    "Get one at https://etherscan.io/myapikey"
                )

            def on_progress(msg):
                click.echo(msg)

            result = volume_data.fetch_agent_volume_basescan(
                basescan_api_key=vs.basescan_api_key,
                sample_agents=20,
                progress_callback=on_progress,
            )

            volume_store.save_agents(conn, result["agents"])
            volume_store.save_transfers(conn, result["transfers"])
            saved = volume_store.save_daily_volumes(
                conn, result["daily_volumes"], source="basescan"
            )
            click.echo()
            click.echo(f"Agents discovered: {len(result['agents'])}")
            click.echo(f"Transfers found: {len(result['transfers'])}")
            click.echo(f"Daily records saved: {saved}")

        elif source == "demo":
            click.echo(f"Loading demo data based on x402 protocol metrics ({days} days)...")
            click.echo("(Set DUNE_API_KEY for real on-chain data)")
            click.echo()
            volumes = volume_data.fetch_demo_data(days=days)
            saved = volume_store.save_daily_volumes(conn, volumes, source="demo")
            click.echo(f"Saved {saved} daily records.")

        # Show summary
        click.echo()
        volumes = volume_store.get_daily_volumes(conn, days=min(days, 7))
        if volumes:
            click.echo(volume_chart.text_daily_summary(volumes))

    finally:
        conn.close()


@volume.command()
def changes():
    """Show day-over-day volume changes."""
    vs = load_volume_settings()
    conn = volume_store.init_db(vs.volume_db_path)

    try:
        diffs = volume_store.get_daily_changes(conn)
    finally:
        conn.close()

    if not diffs:
        click.echo("Need at least 2 days of data. Run 'volume fetch' again tomorrow.")
        return

    click.echo(volume_chart.text_changes(diffs))


@volume.command()
@click.option("--days", default=30, help="Number of days of history (default: 30)")
@click.option("--save", is_flag=True, help="Also save PNG charts to disk")
def chart(days, save):
    """Display agent-to-agent volume charts in the terminal."""
    vs = load_volume_settings()
    conn = volume_store.init_db(vs.volume_db_path)

    try:
        volumes = volume_store.get_daily_volumes(conn, days=days)
        diffs = volume_store.get_daily_changes(conn)
        pairs = volume_store.get_top_agent_pairs(conn, days=days)
    finally:
        conn.close()

    if not volumes:
        click.echo("No data yet. Run 'volume fetch' first.")
        return

    click.echo(volume_chart.text_volume_trend(volumes))
    click.echo(volume_chart.text_tx_count_trend(volumes))

    if diffs:
        click.echo(volume_chart.text_changes(diffs))

    if pairs:
        click.echo(volume_chart.text_top_pairs(pairs))

    if save:
        generated = []
        generated.append(volume_chart.chart_volume_trend(volumes, vs.chart_output_dir))
        generated.append(volume_chart.chart_tx_count_trend(volumes, vs.chart_output_dir))
        click.echo(f"Saved {len(generated)} PNG chart(s):")
        for p in generated:
            click.echo(f"  {p}")


@volume.command()
@click.option("--limit", default=20, help="Number of recent transfers (default: 20)")
def transfers(limit):
    """Show recent agent-to-agent transfers."""
    vs = load_volume_settings()
    conn = volume_store.init_db(vs.volume_db_path)

    try:
        txns = volume_store.get_recent_transfers(conn, limit=limit)
    finally:
        conn.close()

    if not txns:
        click.echo("No transfers recorded. Run 'volume fetch --source basescan' first.")
        return

    click.echo(f"  {'Date':<12} {'From':<14} {'To':<14} {'Value':>12}  {'Tx Hash'}")
    click.echo("  " + "-" * 70)
    for tx in txns:
        f_addr = tx["from_agent"][:6] + "…" + tx["from_agent"][-4:]
        t_addr = tx["to_agent"][:6] + "…" + tx["to_agent"][-4:]
        val = f"${tx['value_usd']:,.2f}"
        tx_hash = tx["tx_hash"][:10] + "…"
        click.echo(f"  {tx['date']:<12} {f_addr:<14} {t_addr:<14} {val:>12}  {tx_hash}")


@volume.command()
def agents():
    """Show known ERC-8004 registered agents."""
    vs = load_volume_settings()
    conn = volume_store.init_db(vs.volume_db_path)

    try:
        count = volume_store.get_agent_count(conn)
        pairs = volume_store.get_top_agent_pairs(conn)
    finally:
        conn.close()

    click.echo(f"Known ERC-8004 agents: {count}")
    if pairs:
        click.echo()
        click.echo(volume_chart.text_top_pairs(pairs))


@volume.command()
def status():
    """Show data source status and summary."""
    vs = load_volume_settings()

    click.echo("  Agent-to-Agent Volume Monitor — Status")
    click.echo()
    click.echo(f"  Dune API key:     {'✓ configured' if vs.dune_api_key else '✗ not set'}")
    click.echo(f"  Basescan API key: {'✓ configured' if vs.basescan_api_key else '✗ not set'}")
    click.echo(f"  Database:         {vs.volume_db_path}")
    click.echo()

    conn = volume_store.init_db(vs.volume_db_path)
    try:
        volumes = volume_store.get_daily_volumes(conn, days=7)
        agent_count = volume_store.get_agent_count(conn)
    finally:
        conn.close()

    click.echo(f"  Known agents:     {agent_count}")
    click.echo(f"  Days of data:     {len(volumes)}")

    if volumes:
        total_vol = sum(v["volume_usd"] for v in volumes)
        total_tx = sum(v["tx_count"] for v in volumes)
        click.echo(f"  Last 7d volume:   {volume_chart._format_volume(total_vol)}")
        click.echo(f"  Last 7d txns:     {total_tx}")
    click.echo()


if __name__ == "__main__":
    main()
