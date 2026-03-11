"""Generate agent-to-agent transaction volume charts (PNG + terminal ASCII)."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime


def _ensure_dir(output_dir: str) -> Path:
    p = Path(output_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _format_volume(v: float) -> str:
    if v >= 1e9:
        return f"${v / 1e9:.1f}B"
    if v >= 1e6:
        return f"${v / 1e6:.1f}M"
    if v >= 1e3:
        return f"${v / 1e3:.1f}K"
    return f"${v:.0f}"


def _format_count(n: int) -> str:
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{n / 1e3:.1f}K"
    return str(n)


# ---------------------------------------------------------------------------
# Terminal (ASCII) chart functions
# ---------------------------------------------------------------------------

BAR_WIDTH = 40


def text_volume_trend(daily_volumes: list[dict]) -> str:
    """Render daily agent-to-agent volume as terminal chart."""
    if not daily_volumes:
        return "No volume data."

    dates = [d["date"] for d in daily_volumes]
    volumes = [d["volume_usd"] for d in daily_volumes]

    max_vol = max(volumes) if volumes else 1
    min_vol = min(volumes) if volumes else 0
    chart_height = 8

    lines = ["  Agent-to-Agent Daily Transaction Volume (USDC)", ""]

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

    lines.append(f"  {'':>8} └{'─' * len(volumes)}")

    if len(dates) >= 3:
        mid = len(dates) // 2
        line = f"  {'':>9}{dates[0][5:]}"
        gap1 = mid - len(dates[0][5:])
        line += " " * max(1, gap1) + dates[mid][5:]
        gap2 = len(dates) - mid - len(dates[mid][5:])
        line += " " * max(1, gap2 - len(dates[-1][5:])) + dates[-1][5:]
        lines.append(line)
    elif len(dates) >= 2:
        lines.append(f"  {'':>9}{dates[0][5:]}{' ' * max(1, len(dates) - 10)}{dates[-1][5:]}")

    lines.append("")
    return "\n".join(lines)


def text_tx_count_trend(daily_volumes: list[dict]) -> str:
    """Render daily transaction count as terminal chart."""
    if not daily_volumes:
        return "No data."

    dates = [d["date"] for d in daily_volumes]
    counts = [d["tx_count"] for d in daily_volumes]

    max_c = max(counts) if counts else 1
    min_c = min(counts) if counts else 0
    chart_height = 6

    lines = ["  Agent-to-Agent Daily Transaction Count", ""]

    for row in range(chart_height, 0, -1):
        threshold = min_c + (max_c - min_c) * row / chart_height
        label = _format_count(int(threshold))
        cells = ""
        for c in counts:
            if c >= threshold:
                cells += "█"
            elif c >= threshold - (max_c - min_c) / chart_height / 2:
                cells += "▄"
            else:
                cells += " "
        lines.append(f"  {label:>8} │{cells}")

    lines.append(f"  {'':>8} └{'─' * len(counts)}")

    if len(dates) >= 2:
        lines.append(f"  {'':>9}{dates[0][5:]}{' ' * max(1, len(dates) - 10)}{dates[-1][5:]}")

    lines.append("")
    return "\n".join(lines)


def text_daily_summary(daily_volumes: list[dict]) -> str:
    """Render a table of daily volumes."""
    if not daily_volumes:
        return "No data."

    lines = [
        "  Date        Transactions    Volume (USDC)     Agents",
        "  " + "-" * 55,
    ]
    for d in daily_volumes:
        vol = _format_volume(d["volume_usd"])
        agents = d.get("unique_agents", "?")
        lines.append(
            f"  {d['date']}  {d['tx_count']:>12}    {vol:>13}    {agents:>6}"
        )
    lines.append("")
    return "\n".join(lines)


def text_changes(changes: list[dict]) -> str:
    """Render day-over-day changes."""
    if not changes:
        return "Need 2+ days of data to show changes."

    c = changes[0]
    lines = ["  Agent-to-Agent Volume — Daily Change", ""]

    vol_arrow = "▲" if (c["volume_change_pct"] or 0) >= 0 else "▼"
    tx_arrow = "▲" if (c["tx_count_change_pct"] or 0) >= 0 else "▼"

    lines.append(f"  Volume:       {_format_volume(c['yesterday_volume'])} → {_format_volume(c['today_volume'])}  "
                 f"{vol_arrow} {c['volume_change_pct']:+.1f}%" if c["volume_change_pct"] is not None
                 else f"  Volume:       {_format_volume(c['yesterday_volume'])} → {_format_volume(c['today_volume'])}  NEW")

    lines.append(f"  Transactions: {c['yesterday_tx_count']} → {c['today_tx_count']}  "
                 f"{tx_arrow} {c['tx_count_change_pct']:+.1f}%" if c["tx_count_change_pct"] is not None
                 else f"  Transactions: {c['yesterday_tx_count']} → {c['today_tx_count']}  NEW")

    # Visual bar comparison
    max_v = max(c["today_volume"], c["yesterday_volume"]) or 1
    y_bar = int(c["yesterday_volume"] / max_v * BAR_WIDTH)
    t_bar = int(c["today_volume"] / max_v * BAR_WIDTH)
    lines.append("")
    lines.append(f"  Yesterday  {'█' * y_bar}{'░' * (BAR_WIDTH - y_bar)}  {_format_volume(c['yesterday_volume'])}")
    lines.append(f"  Today      {'█' * t_bar}{'░' * (BAR_WIDTH - t_bar)}  {_format_volume(c['today_volume'])}")
    lines.append("")
    return "\n".join(lines)


def text_top_pairs(pairs: list[dict], top_n: int = 10) -> str:
    """Render top agent pairs by transaction value."""
    if not pairs:
        return "No agent pair data."

    pairs = pairs[:top_n]
    lines = ["  Top Agent-to-Agent Pairs by Value", ""]
    lines.append(f"  {'From':<14} {'To':<14} {'Txns':>6}  {'Total Value':>12}")
    lines.append("  " + "-" * 50)
    for p in pairs:
        f_addr = p["from_agent"][:6] + "…" + p["from_agent"][-4:]
        t_addr = p["to_agent"][:6] + "…" + p["to_agent"][-4:]
        lines.append(
            f"  {f_addr:<14} {t_addr:<14} {p['tx_count']:>6}  {_format_volume(p['total_value']):>12}"
        )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PNG chart functions (with --save flag)
# ---------------------------------------------------------------------------

def chart_volume_trend(daily_volumes: list[dict], output_dir: str = "./charts") -> str:
    """Line chart of daily agent-to-agent volume. Returns PNG path."""
    dates = [datetime.strptime(d["date"], "%Y-%m-%d") for d in daily_volumes]
    volumes = [d["volume_usd"] for d in daily_volumes]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(dates, volumes, color="#4A90D9", linewidth=2, marker="o", markersize=4)
    ax.fill_between(dates, volumes, alpha=0.15, color="#4A90D9")

    ax.set_xlabel("Date")
    ax.set_ylabel("Volume (USDC)")
    ax.set_title("Agent-to-Agent Daily Transaction Volume")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: _format_volume(x)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    out = _ensure_dir(output_dir) / "agent_volume_trend.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return str(out)


def chart_tx_count_trend(daily_volumes: list[dict], output_dir: str = "./charts") -> str:
    """Bar chart of daily transaction counts. Returns PNG path."""
    dates = [datetime.strptime(d["date"], "%Y-%m-%d") for d in daily_volumes]
    counts = [d["tx_count"] for d in daily_volumes]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(dates, counts, color="#2ECC71", width=0.8)

    ax.set_xlabel("Date")
    ax.set_ylabel("Transaction Count")
    ax.set_title("Agent-to-Agent Daily Transactions")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    out = _ensure_dir(output_dir) / "agent_tx_count.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return str(out)
