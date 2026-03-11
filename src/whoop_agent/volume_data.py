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
