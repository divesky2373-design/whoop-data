"""Generate trading volume visualization charts."""

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime


def _ensure_dir(output_dir: str) -> Path:
    """Create output directory if it doesn't exist."""
    p = Path(output_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _format_volume(v: float) -> str:
    """Format volume for display (e.g. 1.2B, 345M, 12K)."""
    if v >= 1e9:
        return f"${v / 1e9:.1f}B"
    if v >= 1e6:
        return f"${v / 1e6:.1f}M"
    if v >= 1e3:
        return f"${v / 1e3:.0f}K"
    return f"${v:.0f}"


def chart_top_volumes(
    snapshot: dict, output_dir: str = "./charts", top_n: int = 15
) -> str:
    """Horizontal bar chart of top tokens by 24h volume.

    Args:
        snapshot: A single snapshot dict with 'date' and 'tokens' list.
        output_dir: Directory to save the chart.
        top_n: Number of tokens to show.

    Returns:
        Path to the saved PNG file.
    """
    tokens = sorted(
        snapshot["tokens"], key=lambda t: t["volume_usd"], reverse=True
    )[:top_n]
    tokens.reverse()  # matplotlib barh draws bottom-to-top

    names = [f"{t['symbol']}" for t in tokens]
    volumes = [t["volume_usd"] for t in tokens]

    fig, ax = plt.subplots(figsize=(10, max(6, len(tokens) * 0.4)))
    bars = ax.barh(names, volumes, color="#4A90D9", edgecolor="none")

    for bar, vol in zip(bars, volumes):
        ax.text(
            bar.get_width() + max(volumes) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            _format_volume(vol),
            va="center",
            fontsize=8,
        )

    ax.set_xlabel("24h Trading Volume (USD)")
    ax.set_title(f"AI Agent Token Trading Volume — {snapshot['date']}")
    ax.xaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: _format_volume(x))
    )
    plt.tight_layout()

    out = _ensure_dir(output_dir) / f"top_volumes_{snapshot['date']}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return str(out)


def chart_volume_trend(
    token_history: list[dict],
    token_name: str,
    output_dir: str = "./charts",
) -> str:
    """Line chart of a token's daily volume over time.

    Args:
        token_history: List of dicts with 'date' and 'volume_usd'.
        token_name: Display name for the token.
        output_dir: Directory to save the chart.

    Returns:
        Path to the saved PNG file.
    """
    dates = [datetime.strptime(d["date"], "%Y-%m-%d") for d in token_history]
    volumes = [d["volume_usd"] for d in token_history]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(dates, volumes, color="#4A90D9", linewidth=2, marker="o", markersize=4)
    ax.fill_between(dates, volumes, alpha=0.15, color="#4A90D9")

    ax.set_xlabel("Date")
    ax.set_ylabel("Daily Volume (USD)")
    ax.set_title(f"{token_name} — Daily Trading Volume Trend")
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: _format_volume(x))
    )
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    safe_name = token_name.replace(" ", "_").lower()
    out = _ensure_dir(output_dir) / f"trend_{safe_name}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return str(out)


def chart_daily_changes(
    changes: list[dict], output_dir: str = "./charts", top_n: int = 15
) -> str:
    """Bar chart showing day-over-day volume % changes.

    Green bars for increases, red for decreases.

    Args:
        changes: List from volume_store.get_daily_changes().
        output_dir: Directory to save the chart.
        top_n: Number of tokens to show.

    Returns:
        Path to the saved PNG file.
    """
    # Filter out tokens with no change data
    valid = [c for c in changes if c["change_pct"] is not None]
    # Sort by absolute change to show most significant
    valid.sort(key=lambda c: abs(c["change_pct"]), reverse=True)
    valid = valid[:top_n]
    valid.reverse()

    if not valid:
        return ""

    names = [c["symbol"] for c in valid]
    pcts = [c["change_pct"] for c in valid]
    colors = ["#2ECC71" if p >= 0 else "#E74C3C" for p in pcts]

    fig, ax = plt.subplots(figsize=(10, max(6, len(valid) * 0.4)))
    bars = ax.barh(names, pcts, color=colors, edgecolor="none")

    for bar, pct in zip(bars, pcts):
        x_pos = bar.get_width()
        offset = max(abs(p) for p in pcts) * 0.02
        if pct >= 0:
            x_pos += offset
        else:
            x_pos -= offset
        ax.text(
            x_pos,
            bar.get_y() + bar.get_height() / 2,
            f"{pct:+.1f}%",
            va="center",
            ha="left" if pct >= 0 else "right",
            fontsize=8,
        )

    ax.axvline(x=0, color="gray", linewidth=0.8)
    ax.set_xlabel("Volume Change (%)")
    ax.set_title("AI Agent Token — Daily Volume Change")
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()

    out = _ensure_dir(output_dir) / "daily_changes.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return str(out)


def chart_aggregate_volume(
    snapshots: list[dict], output_dir: str = "./charts"
) -> str:
    """Line chart of total AI agent volume over time.

    Args:
        snapshots: List from volume_store.get_snapshots().
        output_dir: Directory to save the chart.

    Returns:
        Path to the saved PNG file.
    """
    if not snapshots:
        return ""

    dates = [
        datetime.strptime(s["date"], "%Y-%m-%d") for s in snapshots
    ]
    totals = [
        sum(t["volume_usd"] for t in s["tokens"]) for s in snapshots
    ]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(dates, totals, color="#9B59B6", linewidth=2, marker="o", markersize=4)
    ax.fill_between(dates, totals, alpha=0.15, color="#9B59B6")

    ax.set_xlabel("Date")
    ax.set_ylabel("Total Volume (USD)")
    ax.set_title("AI Agent Tokens — Aggregate Daily Trading Volume")
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: _format_volume(x))
    )
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    out = _ensure_dir(output_dir) / "aggregate_volume.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return str(out)
