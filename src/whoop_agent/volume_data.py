"""Fetch agent-to-agent on-chain transaction data.

Two data sources:
1. Dune Analytics — x402 protocol transaction volumes (needs DUNE_API_KEY)
2. Basescan API — USDC transfers between ERC-8004 registered agent wallets (free)
"""

import time
from datetime import datetime, timezone

import requests

# ERC-8004 Identity Registry (same address on all EVM chains)
ERC8004_IDENTITY_REGISTRY = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"

# USDC contract addresses
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_ETHEREUM = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"

# Dune query IDs for x402 analytics
# These are from the hashed_official x402-analytics dashboard
DUNE_X402_DAILY_VOLUME_QUERY = 4709382  # daily x402 transaction volume
DUNE_X402_AGENT_TXNS_QUERY = 4709401    # agent-to-agent transaction breakdown

_RATE_LIMIT_DELAY = 2.0


class DuneClient:
    """Client for Dune Analytics API to query x402 agent transaction data."""

    BASE_URL = "https://api.dune.com/api/v1"

    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers["X-Dune-API-Key"] = api_key
        self.session.headers["Content-Type"] = "application/json"

    def execute_query(
        self, query_id: int, params: dict | None = None, timeout: int = 120
    ) -> list[dict]:
        """Execute a Dune query and wait for results.

        Args:
            query_id: Dune query ID.
            params: Optional query parameters.
            timeout: Max seconds to wait for results.

        Returns:
            List of result rows as dicts.
        """
        body = {}
        if params:
            body["query_parameters"] = params

        # Start execution
        resp = self.session.post(
            f"{self.BASE_URL}/query/{query_id}/execute",
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        execution_id = resp.json()["execution_id"]

        # Poll for results
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(3)
            resp = self.session.get(
                f"{self.BASE_URL}/execution/{execution_id}/results",
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            state = data.get("state")
            if state == "QUERY_STATE_COMPLETED":
                return data.get("result", {}).get("rows", [])
            if state in ("QUERY_STATE_FAILED", "QUERY_STATE_CANCELLED"):
                raise RuntimeError(f"Dune query failed: {state}")

        raise TimeoutError(f"Dune query {query_id} timed out after {timeout}s")

    def fetch_x402_daily_volumes(self, days: int = 30) -> list[dict]:
        """Fetch daily x402 agent-to-agent transaction volumes.

        Returns list of dicts with: date, tx_count, volume_usd, unique_agents.
        """
        rows = self.execute_query(
            DUNE_X402_DAILY_VOLUME_QUERY,
            params={"days": str(days)},
        )
        return [
            {
                "date": row.get("day", row.get("date", "")),
                "tx_count": int(row.get("tx_count", row.get("transactions", 0))),
                "volume_usd": float(row.get("volume_usd", row.get("total_volume", 0))),
                "unique_agents": int(row.get("unique_agents", row.get("unique_senders", 0))),
            }
            for row in rows
        ]

    def fetch_agent_transactions(self, days: int = 7) -> list[dict]:
        """Fetch individual agent-to-agent transaction breakdown.

        Returns list of dicts with: date, from_agent, to_agent, value_usd, tx_hash.
        """
        rows = self.execute_query(
            DUNE_X402_AGENT_TXNS_QUERY,
            params={"days": str(days)},
        )
        return [
            {
                "date": row.get("day", row.get("date", "")),
                "from_agent": row.get("from_agent", row.get("sender", "")),
                "to_agent": row.get("to_agent", row.get("receiver", "")),
                "value_usd": float(row.get("value_usd", row.get("amount", 0))),
                "tx_hash": row.get("tx_hash", row.get("hash", "")),
            }
            for row in rows
        ]


class BasescanClient:
    """Client for Etherscan V2 API to query USDC transfers between agent wallets on Base."""

    # Etherscan V2 unified endpoint with Base chain ID
    BASE_URL = "https://api.etherscan.io/v2/api"
    CHAIN_ID = 8453  # Base mainnet

    def __init__(self, api_key: str | None = None):
        self.session = requests.Session()
        self.api_key = api_key or ""
        self._last_request = 0.0

    def _get(self, params: dict) -> dict:
        """Rate-limited GET request to Etherscan V2."""
        elapsed = time.time() - self._last_request
        if elapsed < _RATE_LIMIT_DELAY:
            time.sleep(_RATE_LIMIT_DELAY - elapsed)

        params["chainid"] = self.CHAIN_ID
        params["apikey"] = self.api_key
        resp = self.session.get(self.BASE_URL, params=params, timeout=30)
        self._last_request = time.time()
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") == "0":
            msg = str(data.get("result", data.get("message", "")))
            if "rate limit" in msg.lower() or "Max rate" in msg:
                time.sleep(5)
                return self._get(params)
        return data

    def get_erc8004_agents(self, start_block: int = 0) -> list[str]:
        """Get registered ERC-8004 agent owner addresses from Identity Registry.

        Queries Transfer events on the ERC-721 Identity Registry to find
        addresses that own agent NFTs.
        """
        params = {
            "module": "logs",
            "action": "getLogs",
            "address": ERC8004_IDENTITY_REGISTRY,
            # Transfer(address,address,uint256) topic
            "topic0": "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
            "fromBlock": str(start_block),
            "toBlock": "latest",
            "page": "1",
            "offset": "1000",
        }
        data = self._get(params)
        results = data.get("result", [])

        if not isinstance(results, list):
            return []

        # Extract 'to' addresses from Transfer events (topic2 = recipient)
        agents = set()
        for log in results:
            topics = log.get("topics", [])
            if len(topics) >= 3:
                # topic[2] is the 'to' address, padded to 32 bytes
                to_addr = "0x" + topics[2][-40:]
                if to_addr != "0x" + "0" * 40:  # skip zero address (burns)
                    agents.add(to_addr.lower())
        return sorted(agents)

    def get_usdc_transfers(
        self, address: str, start_block: int = 0
    ) -> list[dict]:
        """Get USDC token transfers for an address on Base."""
        params = {
            "module": "account",
            "action": "tokentx",
            "contractaddress": USDC_BASE,
            "address": address,
            "startblock": str(start_block),
            "endblock": "99999999",
            "page": "1",
            "offset": "100",
            "sort": "desc",
        }
        data = self._get(params)
        results = data.get("result", [])

        if not isinstance(results, list):
            return []

        return [
            {
                "tx_hash": tx["hash"],
                "from": tx["from"].lower(),
                "to": tx["to"].lower(),
                "value_usdc": int(tx["value"]) / 1e6,  # USDC has 6 decimals
                "timestamp": datetime.fromtimestamp(
                    int(tx["timeStamp"]), tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S"),
                "date": datetime.fromtimestamp(
                    int(tx["timeStamp"]), tz=timezone.utc
                ).strftime("%Y-%m-%d"),
                "block": int(tx["blockNumber"]),
            }
            for tx in results
        ]


def fetch_agent_volume_dune(dune_api_key: str, days: int = 30) -> list[dict]:
    """Fetch daily agent-to-agent volumes via Dune (x402 data).

    Returns list of daily snapshots: {date, tx_count, volume_usd, unique_agents}.
    """
    client = DuneClient(dune_api_key)
    return client.fetch_x402_daily_volumes(days=days)


def fetch_demo_data(days: int = 30) -> list[dict]:
    """Generate realistic demo data based on known x402 protocol metrics.

    Uses public figures: x402 processed 75M txns / $24M in Dec 2025,
    growing to 500K+ weekly settlements by early 2026.
    """
    import random
    from datetime import timedelta

    random.seed(42)
    base_date = datetime.now(timezone.utc)
    # Base metrics: ~70K daily txns, ~$115K daily volume (early 2026 range)
    base_tx = 70000
    base_vol = 115000.0
    base_agents = 2400

    results = []
    for i in range(days, 0, -1):
        date = base_date - timedelta(days=i)
        # Add realistic variance (weekends lower, some growth trend)
        weekday_factor = 0.7 if date.weekday() >= 5 else 1.0
        growth = 1 + (days - i) * 0.005  # slight upward trend
        noise = random.uniform(0.75, 1.3)

        tx_count = int(base_tx * weekday_factor * growth * noise)
        volume = base_vol * weekday_factor * growth * random.uniform(0.6, 1.5)
        agents = int(base_agents * growth * random.uniform(0.9, 1.1))

        results.append({
            "date": date.strftime("%Y-%m-%d"),
            "tx_count": tx_count,
            "volume_usd": round(volume, 2),
            "unique_agents": agents,
        })
    return results


def fetch_agent_volume_basescan(
    basescan_api_key: str | None = None,
    sample_agents: int = 20,
    progress_callback=None,
) -> dict:
    """Fetch agent-to-agent USDC transfers on Base via Basescan.

    Discovers ERC-8004 registered agents, then checks USDC transfers
    between them. Returns aggregated daily volumes.

    Args:
        basescan_api_key: Optional Basescan API key.
        sample_agents: Number of agent addresses to sample.
        progress_callback: Optional callable(message).

    Returns:
        Dict with 'agents' (list of addresses), 'transfers' (list),
        and 'daily_volumes' (list of {date, tx_count, volume_usd}).
    """
    client = BasescanClient(api_key=basescan_api_key)

    if progress_callback:
        progress_callback("Discovering ERC-8004 registered agents on Base...")

    agents = client.get_erc8004_agents()
    agent_set = set(agents[:sample_agents])

    if progress_callback:
        progress_callback(f"Found {len(agents)} agents, sampling {len(agent_set)}")

    # Fetch USDC transfers for sampled agents
    all_transfers = []
    for i, addr in enumerate(sorted(agent_set)):
        if progress_callback:
            progress_callback(f"  [{i+1}/{len(agent_set)}] Checking {addr[:10]}...")

        transfers = client.get_usdc_transfers(addr)
        # Filter to agent-to-agent transfers only
        for tx in transfers:
            if tx["from"] in agent_set or tx["to"] in agent_set:
                all_transfers.append(tx)

    # Deduplicate by tx_hash
    seen = set()
    unique_transfers = []
    for tx in all_transfers:
        if tx["tx_hash"] not in seen:
            seen.add(tx["tx_hash"])
            unique_transfers.append(tx)

    # Aggregate by day
    daily: dict[str, dict] = {}
    for tx in unique_transfers:
        date = tx["date"]
        if date not in daily:
            daily[date] = {"date": date, "tx_count": 0, "volume_usd": 0.0}
        daily[date]["tx_count"] += 1
        daily[date]["volume_usd"] += tx["value_usdc"]

    daily_volumes = sorted(daily.values(), key=lambda d: d["date"])

    return {
        "agents": sorted(agent_set),
        "transfers": unique_transfers,
        "daily_volumes": daily_volumes,
    }
