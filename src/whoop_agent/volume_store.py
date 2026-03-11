"""Local SQLite storage for agent-to-agent transaction volume data."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = str(Path.home() / ".whoop_agent_volume.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_volumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'dune',
    tx_count INTEGER NOT NULL DEFAULT 0,
    volume_usd REAL NOT NULL DEFAULT 0,
    unique_agents INTEGER DEFAULT 0,
    fetched_at TEXT NOT NULL,
    UNIQUE(date, source)
);

CREATE TABLE IF NOT EXISTS agent_transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_hash TEXT NOT NULL,
    date TEXT NOT NULL,
    from_agent TEXT NOT NULL,
    to_agent TEXT NOT NULL,
    value_usd REAL NOT NULL,
    source TEXT NOT NULL DEFAULT 'basescan',
    UNIQUE(tx_hash)
);

CREATE TABLE IF NOT EXISTS known_agents (
    address TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'erc8004'
);

CREATE INDEX IF NOT EXISTS idx_volumes_date ON daily_volumes(date);
CREATE INDEX IF NOT EXISTS idx_transfers_date ON agent_transfers(date);
"""


def init_db(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Initialize the database and return a connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def save_daily_volumes(
    conn: sqlite3.Connection, volumes: list[dict], source: str = "dune"
) -> int:
    """Save daily volume records. Returns number of rows saved."""
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    for v in volumes:
        conn.execute(
            "INSERT INTO daily_volumes (date, source, tx_count, volume_usd, "
            "  unique_agents, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(date, source) DO UPDATE SET "
            "  tx_count=excluded.tx_count, volume_usd=excluded.volume_usd, "
            "  unique_agents=excluded.unique_agents, fetched_at=excluded.fetched_at",
            (
                v["date"],
                source,
                v.get("tx_count", 0),
                v.get("volume_usd", 0),
                v.get("unique_agents", 0),
                now,
            ),
        )
        count += 1
    conn.commit()
    return count


def save_transfers(
    conn: sqlite3.Connection, transfers: list[dict], source: str = "basescan"
) -> int:
    """Save agent-to-agent transfer records. Returns count saved."""
    count = 0
    for tx in transfers:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO agent_transfers "
                "(tx_hash, date, from_agent, to_agent, value_usd, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    tx["tx_hash"],
                    tx["date"],
                    tx.get("from_agent", tx.get("from", "")),
                    tx.get("to_agent", tx.get("to", "")),
                    tx["value_usd"] if "value_usd" in tx else tx.get("value_usdc", 0),
                    source,
                ),
            )
            count += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    return count


def save_agents(conn: sqlite3.Connection, addresses: list[str]) -> int:
    """Save known agent addresses. Returns count of new agents."""
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    for addr in addresses:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO known_agents (address, first_seen, source) "
                "VALUES (?, ?, 'erc8004')",
                (addr.lower(), now),
            )
            count += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    return count


def get_daily_volumes(
    conn: sqlite3.Connection, days: int = 30, source: str | None = None
) -> list[dict]:
    """Get daily volume records, most recent first then reversed."""
    if source:
        rows = conn.execute(
            "SELECT date, tx_count, volume_usd, unique_agents, source "
            "FROM daily_volumes WHERE source = ? "
            "ORDER BY date DESC LIMIT ?",
            (source, days),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT date, SUM(tx_count) as tx_count, SUM(volume_usd) as volume_usd, "
            "  MAX(unique_agents) as unique_agents, GROUP_CONCAT(DISTINCT source) as source "
            "FROM daily_volumes GROUP BY date "
            "ORDER BY date DESC LIMIT ?",
            (days,),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_daily_changes(conn: sqlite3.Connection) -> list[dict]:
    """Compare latest two days of volume data.

    Returns list with one entry containing today/yesterday comparison.
    """
    rows = conn.execute(
        "SELECT date, SUM(tx_count) as tx_count, SUM(volume_usd) as volume_usd "
        "FROM daily_volumes GROUP BY date ORDER BY date DESC LIMIT 2"
    ).fetchall()

    if len(rows) < 2:
        return []

    today, yesterday = dict(rows[0]), dict(rows[1])
    yv = yesterday["volume_usd"]
    tv = today["volume_usd"]
    vol_pct = ((tv - yv) / yv * 100) if yv > 0 else None

    ytc = yesterday["tx_count"]
    ttc = today["tx_count"]
    tx_pct = ((ttc - ytc) / ytc * 100) if ytc > 0 else None

    return [{
        "today_date": today["date"],
        "yesterday_date": yesterday["date"],
        "today_volume": tv,
        "yesterday_volume": yv,
        "volume_change_pct": round(vol_pct, 2) if vol_pct is not None else None,
        "today_tx_count": ttc,
        "yesterday_tx_count": ytc,
        "tx_count_change_pct": round(tx_pct, 2) if tx_pct is not None else None,
    }]


def get_recent_transfers(
    conn: sqlite3.Connection, limit: int = 20
) -> list[dict]:
    """Get most recent agent-to-agent transfers."""
    rows = conn.execute(
        "SELECT tx_hash, date, from_agent, to_agent, value_usd, source "
        "FROM agent_transfers ORDER BY date DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_top_agent_pairs(
    conn: sqlite3.Connection, days: int = 30
) -> list[dict]:
    """Get top agent pairs by transaction value."""
    rows = conn.execute(
        "SELECT from_agent, to_agent, COUNT(*) as tx_count, "
        "  SUM(value_usd) as total_value "
        "FROM agent_transfers "
        "WHERE date >= date('now', ? || ' days') "
        "GROUP BY from_agent, to_agent "
        "ORDER BY total_value DESC LIMIT 20",
        (f"-{days}",),
    ).fetchall()
    return [dict(r) for r in rows]


def get_agent_count(conn: sqlite3.Connection) -> int:
    """Get total number of known agents."""
    row = conn.execute("SELECT COUNT(*) as cnt FROM known_agents").fetchone()
    return row["cnt"] if row else 0
