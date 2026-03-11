"""Fetch AI agent token trading volume data from CoinGecko."""

import time
from datetime import datetime, timezone

import requests

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
COINGECKO_PRO_BASE = "https://pro-api.coingecko.com/api/v3"

# CoinGecko category for AI agent tokens
AI_AGENT_CATEGORY = "artificial-intelligence"

# Rate limit: ~1.5s between requests for free tier
_RATE_LIMIT_DELAY = 1.5


class CoinGeckoClient:
    """Lightweight CoinGecko API client with rate limiting."""

    def __init__(self, api_key: str | None = None):
        self.session = requests.Session()
        self.api_key = api_key
        if api_key:
            self.base_url = COINGECKO_PRO_BASE
            self.session.headers["x-cg-pro-api-key"] = api_key
        else:
            self.base_url = COINGECKO_BASE
        self._last_request = 0.0

    def _get(self, endpoint: str, params: dict | None = None) -> dict | list:
        """Make a rate-limited GET request."""
        elapsed = time.time() - self._last_request
        if elapsed < _RATE_LIMIT_DELAY:
            time.sleep(_RATE_LIMIT_DELAY - elapsed)

        url = f"{self.base_url}{endpoint}"
        resp = self.session.get(url, params=params, timeout=30)
        self._last_request = time.time()
        resp.raise_for_status()
        return resp.json()

    def fetch_ai_agent_tokens(self, limit: int = 20) -> list[dict]:
        """Fetch top AI agent tokens by trading volume.

        Returns list of dicts with: coin_id, symbol, name, price_usd,
        market_cap, volume_usd, price_change_24h_pct.
        """
        data = self._get(
            "/coins/markets",
            params={
                "vs_currency": "usd",
                "category": AI_AGENT_CATEGORY,
                "order": "volume_desc",
                "per_page": limit,
                "page": 1,
                "sparkline": "false",
            },
        )

        return [
            {
                "coin_id": coin["id"],
                "symbol": coin["symbol"].upper(),
                "name": coin["name"],
                "price_usd": coin.get("current_price"),
                "market_cap": coin.get("market_cap"),
                "volume_usd": coin.get("total_volume", 0),
                "price_change_24h_pct": coin.get(
                    "price_change_percentage_24h"
                ),
            }
            for coin in data
        ]

    def fetch_token_volume_history(
        self, coin_id: str, days: int = 30
    ) -> list[dict]:
        """Fetch daily volume history for a specific token.

        Returns list of dicts with: date (str), volume_usd (float).
        """
        data = self._get(
            f"/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": days, "interval": "daily"},
        )

        results = []
        for ts, vol in data.get("total_volumes", []):
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            results.append({
                "date": dt.strftime("%Y-%m-%d"),
                "volume_usd": round(vol, 2),
            })
        return results


    def fetch_token_full_history(
        self, coin_id: str, days: int = 30
    ) -> list[dict]:
        """Fetch daily volume, price, and market cap history for a token.

        Returns list of dicts with: date, volume_usd, price_usd, market_cap.
        """
        data = self._get(
            f"/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": days, "interval": "daily"},
        )

        volumes = {}
        for ts, vol in data.get("total_volumes", []):
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            date_str = dt.strftime("%Y-%m-%d")
            volumes[date_str] = vol

        prices = {}
        for ts, price in data.get("prices", []):
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            prices[dt.strftime("%Y-%m-%d")] = price

        mcaps = {}
        for ts, mcap in data.get("market_caps", []):
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            mcaps[dt.strftime("%Y-%m-%d")] = mcap

        results = []
        for date_str in sorted(volumes.keys()):
            results.append({
                "date": date_str,
                "volume_usd": round(volumes[date_str], 2),
                "price_usd": round(prices.get(date_str, 0), 6),
                "market_cap": round(mcaps.get(date_str, 0), 2),
            })
        return results


def fetch_daily_snapshot(
    api_key: str | None = None, limit: int = 20
) -> dict:
    """Fetch a complete daily snapshot of AI agent token volumes.

    Returns dict with: date, fetched_at, tokens list.
    """
    client = CoinGeckoClient(api_key=api_key)
    tokens = client.fetch_ai_agent_tokens(limit=limit)

    now = datetime.now(timezone.utc)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "fetched_at": now.isoformat(),
        "tokens": tokens,
    }


def backfill_snapshots(
    api_key: str | None = None, days: int = 30, limit: int = 15,
    progress_callback=None,
) -> list[dict]:
    """Backfill historical daily snapshots for AI agent tokens.

    Fetches the current top tokens, then pulls each token's daily
    volume/price/mcap history and assembles per-day snapshots.

    Args:
        api_key: Optional CoinGecko API key.
        days: Number of days to backfill.
        limit: Number of top tokens to include.
        progress_callback: Optional callable(token_name, index, total).

    Returns:
        List of snapshot dicts (one per day), sorted chronologically.
    """
    client = CoinGeckoClient(api_key=api_key)

    # Step 1: get current top tokens for their IDs, symbols, names
    tokens = client.fetch_ai_agent_tokens(limit=limit)

    # Step 2: for each token, fetch historical data
    # Structure: {date: {coin_id: {volume, price, mcap}}}
    daily_data: dict[str, dict[str, dict]] = {}

    for i, token in enumerate(tokens):
        if progress_callback:
            progress_callback(token["name"], i + 1, len(tokens))

        history = client.fetch_token_full_history(token["coin_id"], days=days)
        for day in history:
            date_str = day["date"]
            if date_str not in daily_data:
                daily_data[date_str] = {}
            daily_data[date_str][token["coin_id"]] = {
                "coin_id": token["coin_id"],
                "symbol": token["symbol"],
                "name": token["name"],
                "volume_usd": day["volume_usd"],
                "price_usd": day["price_usd"],
                "market_cap": day["market_cap"],
                "price_change_24h_pct": None,  # not available in history
            }

    # Step 3: assemble into snapshot format
    snapshots = []
    for date_str in sorted(daily_data.keys()):
        snapshots.append({
            "date": date_str,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "tokens": list(daily_data[date_str].values()),
        })

    return snapshots
