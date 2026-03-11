"""Configuration and settings management."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    whoop_client_id: str
    whoop_client_secret: str
    anthropic_api_key: str
    redirect_uri: str = "http://localhost:1234"
    token_path: str = str(Path.home() / ".whoop_tokens.json")


@dataclass
class VolumeSettings:
    """Settings for the AI agent trading volume monitor."""

    coingecko_api_key: str | None = None
    volume_db_path: str = str(Path.home() / ".whoop_agent_volume.db")
    chart_output_dir: str = "./charts"


def load_settings() -> Settings:
    """Load settings from .env file and environment variables.

    Raises:
        SystemExit: If required environment variables are missing.
    """
    load_dotenv()

    missing = []
    for var in ["WHOOP_CLIENT_ID", "WHOOP_CLIENT_SECRET", "ANTHROPIC_API_KEY"]:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        raise SystemExit(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Copy .env.example to .env and fill in your credentials."
        )

    return Settings(
        whoop_client_id=os.environ["WHOOP_CLIENT_ID"],
        whoop_client_secret=os.environ["WHOOP_CLIENT_SECRET"],
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        redirect_uri=os.getenv("WHOOP_REDIRECT_URI", "http://localhost:1234"),
        token_path=os.getenv(
            "WHOOP_TOKEN_PATH", str(Path.home() / ".whoop_tokens.json")
        ),
    )


def load_volume_settings() -> VolumeSettings:
    """Load volume monitor settings. No required env vars."""
    load_dotenv()

    return VolumeSettings(
        coingecko_api_key=os.getenv("COINGECKO_API_KEY"),
        volume_db_path=os.getenv(
            "VOLUME_DB_PATH", str(Path.home() / ".whoop_agent_volume.db")
        ),
        chart_output_dir=os.getenv("CHART_OUTPUT_DIR", "./charts"),
    )
