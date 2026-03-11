"""Local SQLite storage for AI agent trading volume data."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = str(Path.home() / ".whoop_agent_volume.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    UNIQUE(date)
);

CREATE TABLE IF NOT EXISTS token_volumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    coin_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    volume_usd REAL NOT NULL,
    market_cap REAL,
    price_usd REAL,
    price_change_24h_pct REAL,
    FOREIGN KEY (snapshot_id) REFERENCES daily_snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_token_coin_snapshot
    ON token_volumes(coin_id, snapshot_id);
"""


def init_db(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Initialize the database and return a connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def save_snapshot(conn: sqlite3.Connection, snapshot: dict) -> int:
    """Save a daily volume snapshot. Returns the snapshot id.

    Args:
        conn: Database connection.
        snapshot: Dict with 'date', 'fetched_at', and 'tokens' list.

    Returns:
        The snapshot row id.
    """
    date_str = snapshot["date"]
    fetched_at = snapshot.get(
        "fetched_at", datetime.now(timezone.utc).isoformat()
    )

    cur = conn.execute(
        "INSERT INTO daily_snapshots (date, fetched_at) VALUES (?, ?) "
        "ON CONFLICT(date) DO UPDATE SET fetched_at = excluded.fetched_at "
        "RETURNING id",
        (date_str, fetched_at),
    )
    snapshot_id = cur.fetchone()[0]

    # Clear old token data for this snapshot (in case of re-fetch)
    conn.execute(
        "DELETE FROM token_volumes WHERE snapshot_id = ?", (snapshot_id,)
    )

    for token in snapshot.get("tokens", []):
        conn.execute(
            "INSERT INTO token_volumes "
            "(snapshot_id, coin_id, symbol, name, volume_usd, "
            " market_cap, price_usd, price_change_24h_pct) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                snapshot_id,
                token["coin_id"],
                token["symbol"],
                token["name"],
                token["volume_usd"],
                token.get("market_cap"),
                token.get("price_usd"),
                token.get("price_change_24h_pct"),
            ),
        )

    conn.commit()
    return snapshot_id


def get_snapshots(conn: sqlite3.Connection, days: int = 30) -> list[dict]:
    """Get the last N days of snapshots with token data."""
    rows = conn.execute(
        "SELECT id, date, fetched_at FROM daily_snapshots "
        "ORDER BY date DESC LIMIT ?",
        (days,),
    ).fetchall()

    results = []
    for row in rows:
        tokens = conn.execute(
            "SELECT coin_id, symbol, name, volume_usd, market_cap, "
            "       price_usd, price_change_24h_pct "
            "FROM token_volumes WHERE snapshot_id = ? "
            "ORDER BY volume_usd DESC",
            (row["id"],),
        ).fetchall()

        results.append({
            "date": row["date"],
            "fetched_at": row["fetched_at"],
            "tokens": [dict(t) for t in tokens],
        })

    return list(reversed(results))  # chronological order


def get_token_history(
    conn: sqlite3.Connection, coin_id: str, days: int = 30
) -> list[dict]:
    """Get volume history for a specific token over N days."""
    rows = conn.execute(
        "SELECT s.date, t.volume_usd, t.price_usd, t.market_cap, "
        "       t.price_change_24h_pct "
        "FROM token_volumes t "
        "JOIN daily_snapshots s ON t.snapshot_id = s.id "
        "WHERE t.coin_id = ? "
        "ORDER BY s.date DESC LIMIT ?",
        (coin_id, days),
    ).fetchall()

    return [dict(r) for r in reversed(rows)]


def get_daily_changes(conn: sqlite3.Connection) -> list[dict]:
    """Compare the latest snapshot to the previous one.

    Returns list of dicts with coin_id, symbol, today_volume,
    yesterday_volume, and change_pct.
    """
    snapshots = conn.execute(
        "SELECT id, date FROM daily_snapshots ORDER BY date DESC LIMIT 2"
    ).fetchall()

    if len(snapshots) < 2:
        return []

    today_id, yesterday_id = snapshots[0]["id"], snapshots[1]["id"]

    today_tokens = {
        r["coin_id"]: dict(r)
        for r in conn.execute(
            "SELECT coin_id, symbol, name, volume_usd "
            "FROM token_volumes WHERE snapshot_id = ?",
            (today_id,),
        ).fetchall()
    }

    yesterday_tokens = {
        r["coin_id"]: dict(r)
        for r in conn.execute(
            "SELECT coin_id, symbol, name, volume_usd "
            "FROM token_volumes WHERE snapshot_id = ?",
            (yesterday_id,),
        ).fetchall()
    }

    changes = []
    for coin_id, today in today_tokens.items():
        yesterday = yesterday_tokens.get(coin_id)
        yv = yesterday["volume_usd"] if yesterday else 0
        tv = today["volume_usd"]
        pct = ((tv - yv) / yv * 100) if yv > 0 else None

        changes.append({
            "coin_id": coin_id,
            "symbol": today["symbol"],
            "name": today["name"],
            "today_volume": tv,
            "yesterday_volume": yv,
            "change_pct": round(pct, 2) if pct is not None else None,
        })

    changes.sort(key=lambda x: x["today_volume"], reverse=True)
    return changes


def list_tracked_tokens(conn: sqlite3.Connection) -> list[dict]:
    """List all unique tokens that have been tracked."""
    rows = conn.execute(
        "SELECT DISTINCT coin_id, symbol, name FROM token_volumes "
        "ORDER BY symbol"
    ).fetchall()
    return [dict(r) for r in rows]
