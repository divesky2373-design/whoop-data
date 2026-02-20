"""WHOOP OAuth2 authentication flow."""

import json
from pathlib import Path

from whoopy import WhoopClient
from whoopy.utils.auth import TokenInfo

from .config import Settings

SCOPES = [
    "read:recovery",
    "read:cycles",
    "read:sleep",
    "read:workout",
    "read:profile",
    "read:body_measurement",
]


def run_auth_flow(settings: Settings) -> WhoopClient:
    """Run the OAuth2 authorization flow and save tokens.

    Opens a browser for the user to authorize the app, then saves
    the resulting tokens to disk.

    Args:
        settings: Application settings with client credentials.

    Returns:
        An authenticated WhoopClient.
    """
    client = WhoopClient.auth_flow(
        client_id=settings.whoop_client_id,
        client_secret=settings.whoop_client_secret,
        redirect_uri=settings.redirect_uri,
        scopes=SCOPES,
        open_browser=True,
    )

    save_tokens(client.token_info, settings.token_path)
    return client


def save_tokens(token_info: TokenInfo, path: str) -> None:
    """Save token information to a JSON file.

    Args:
        token_info: The OAuth2 token data to persist.
        path: File path to save the tokens.
    """
    Path(path).write_text(json.dumps(token_info.to_dict(), indent=2))


def load_tokens(path: str) -> TokenInfo | None:
    """Load token information from a JSON file.

    Args:
        path: File path to load tokens from.

    Returns:
        TokenInfo if file exists and is valid, None otherwise.
    """
    token_file = Path(path)
    if not token_file.exists():
        return None

    data = json.loads(token_file.read_text())
    return TokenInfo.from_dict(data)


def get_client(settings: Settings) -> WhoopClient:
    """Get an authenticated WHOOP client, using saved tokens if available.

    Loads saved tokens and creates a client. If no tokens exist,
    raises an error directing the user to authenticate first.

    Args:
        settings: Application settings.

    Returns:
        An authenticated WhoopClient.

    Raises:
        SystemExit: If no saved tokens are found.
    """
    token_info = load_tokens(settings.token_path)
    if token_info is None:
        raise SystemExit(
            "No saved WHOOP tokens found. Run 'whoop-agent auth' first."
        )

    client = WhoopClient(
        token_info=token_info,
        client_id=settings.whoop_client_id,
        client_secret=settings.whoop_client_secret,
        redirect_uri=settings.redirect_uri,
        auto_refresh_token=True,
    )

    return client
