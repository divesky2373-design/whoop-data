"""Generate trading volume visualization charts (PNG + terminal ASCII)."""

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


# ---------------------------------------------------------------------------
# Terminal (ASCII) chart functions
# ---------------------------------------------------------------------------

BAR_WIDTH = 40  # max width of ASCII bar in characters


def text_top_volumes(snapshot: dict, top_n: int = 15) -> str:
    """Render a horizontal bar chart of top tokens in the terminal."""
    tokens = sorted(
        snapshot["tokens"], key=lambda t: t["volume_usd"], reverse=True
    )[:top_n]

    if not tokens:
        return "No token data."

    max_vol = max(t["volume_usd"] for t in tokens)
    sym_width = max(len(t["symbol"]) for t in tokens)

    lines = [f"  AI Agent Token Trading Volume — {snapshot['date']}", ""]
    for t in tokens:
        ratio = t["volume_usd"] / max_vol if max_vol else 0
        bar_len = int(ratio * BAR_WIDTH)
        bar = "█" * bar_len + "░" * (BAR_WIDTH - bar_len)
        vol_str = _format_volume(t["volume_usd"])
        lines.append(
            f"  {t['symbol']:<{sym_width}}  {bar}  {vol_str}"
        )
    lines.append("")
    return "\n".join(lines)


def text_daily_changes(changes: list[dict], top_n: int = 15) -> str:
    """Render day-over-day volume % changes in the terminal."""
    valid = [c for c in changes if c["change_pct"] is not None]
    valid.sort(key=lambda c: abs(c["change_pct"]), reverse=True)
    valid = valid[:top_n]

    if not valid:
        return "No change data available."

    max_abs = max(abs(c["change_pct"]) for c in valid)
    sym_width = max(len(c["symbol"]) for c in valid)
    half = BAR_WIDTH // 2

    lines = ["  AI Agent Token — Daily Volume Change", ""]

    for c in valid:
        pct = c["change_pct"]
        ratio = abs(pct) / max_abs if max_abs else 0
        bar_len = int(ratio * half)

        if pct >= 0:
            left = " " * half
            right = "▓" * bar_len + " " * (half - bar_len)
            indicator = "▲"
        else:
            padding = half - bar_len
            left = " " * padding + "▓" * bar_len
            right = " " * half
            indicator = "▼"

        pct_str = f"{pct:+.1f}%"
        lines.append(
            f"  {c['symbol']:<{sym_width}}  {left}│{right}  {indicator} {pct_str}"
        )

    lines.append("")
    return "\n".join(lines)


def text_aggregate_volume(snapshots: list[dict]) -> str:
    """Render aggregate volume sparkline-style in terminal."""
    if not snapshots:
        return "No data."

    dates = [s["date"] for s in snapshots]
    totals = [sum(t["volume_usd"] for t in s["tokens"]) for s in snapshots]

    max_vol = max(totals) if totals else 1
    min_vol = min(totals) if totals else 0
    chart_height = 8
    chart_width = len(totals)

    lines = ["  AI Agent Tokens — Aggregate Daily Volume", ""]

    # Build row-by-row from top to bottom
    for row in range(chart_height, 0, -1):
        threshold = min_vol + (max_vol - min_vol) * row / chart_height
        label = _format_volume(threshold)
        cells = ""
        for vol in totals:
            if vol >= threshold:
                cells += "█"
            elif vol >= threshold - (max_vol - min_vol) / chart_height / 2:
                cells += "▄"
            else:
                cells += " "
        lines.append(f"  {label:>8} │{cells}")

    # X-axis
    lines.append(f"  {'':>8} └{'─' * chart_width}")

    # Date labels (first, middle, last)
    if len(dates) >= 3:
        mid = len(dates) // 2
        date_line = f"  {'':>9}{dates[0][5:]}"
        gap1 = mid - len(dates[0][5:])
        date_line += " " * max(1, gap1) + dates[mid][5:]
        gap2 = chart_width - mid - len(dates[mid][5:])
        date_line += " " * max(1, gap2 - len(dates[-1][5:])) + dates[-1][5:]
        lines.append(date_line)
    elif dates:
        lines.append(f"  {'':>9}{dates[0][5:]}{'':>{max(0, chart_width - len(dates[0][5:]))}}{dates[-1][5:] if len(dates) > 1 else ''}")

    lines.append("")
    return "\n".join(lines)


def text_volume_trend(token_history: list[dict], token_name: str) -> str:
    """Render a single token's volume trend in terminal."""
    if not token_history:
        return f"No history for {token_name}."

    dates = [d["date"] for d in token_history]
    volumes = [d["volume_usd"] for d in token_history]

    max_vol = max(volumes) if volumes else 1
    min_vol = min(volumes) if volumes else 0
    chart_height = 8
    chart_width = len(volumes)

    lines = [f"  {token_name} — Daily Trading Volume Trend", ""]

    for row in range(chart_height, 0, -1):
        threshold = min_vol + (max_vol - min_vol) * row / chart_height
        label = _format_volume(threshold)
        cells = ""
        for vol in volumes:
            if vol >= threshold:
                cells += "█"
            elif vol >= threshold - (max_vol - min_vol) / chart_height / 2:
                cells += "▄"
            else:
                cells += " "
        lines.append(f"  {label:>8} │{cells}")

    lines.append(f"  {'':>8} └{'─' * chart_width}")

    if len(dates) >= 2:
        lines.append(f"  {'':>9}{dates[0][5:]}{' ' * max(1, chart_width - len(dates[0][5:]) - len(dates[-1][5:]))}{dates[-1][5:]}")

    lines.append("")
    return "\n".join(lines)


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
