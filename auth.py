"""OAuth authentication for Claude subscription - uses Claude Code's tokens."""

import json
import time
from pathlib import Path

import httpx
from rich.console import Console

from core.config import CONFIG_DIR

console = Console()
TOKENS_FILE = CONFIG_DIR / "tokens.json"

# Claude Code's credentials file
CLAUDE_CODE_CREDENTIALS = Path.home() / ".claude" / ".credentials.json"

# OAuth constants for refresh
OAUTH_TOKEN_URL = "https://claude.ai/oauth/token"


def load_tokens() -> dict | None:
    """Load OAuth tokens - first try our file, then fall back to Claude Code's."""
    # Try our own tokens first
    if TOKENS_FILE.exists():
        tokens = json.loads(TOKENS_FILE.read_text())
        if tokens.get("expires_at", 0) > time.time():
            return tokens
        if "refresh_token" in tokens:
            refreshed = refresh_tokens(tokens["refresh_token"])
            if refreshed:
                return refreshed

    # Fall back to Claude Code's credentials
    if CLAUDE_CODE_CREDENTIALS.exists():
        try:
            creds = json.loads(CLAUDE_CODE_CREDENTIALS.read_text())
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON in Claude Code credentials:[/red] {e}")
            return None

        oauth = creds.get("claudeAiOauth", {})
        if not oauth:
            return None

        tokens = {
            "access_token": oauth.get("accessToken"),
            "refresh_token": oauth.get("refreshToken"),
            "expires_at": oauth.get("expiresAt", 0) / 1000,  # Convert ms to seconds
        }
        if not tokens["access_token"]:
            return None

        # Check if expired
        if tokens["expires_at"] > time.time():
            return tokens
        # Try refresh
        if tokens["refresh_token"]:
            return refresh_tokens(tokens["refresh_token"])

    return None


def save_tokens(tokens: dict):
    """Save OAuth tokens to our file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TOKENS_FILE.write_text(json.dumps(tokens, indent=2))
    TOKENS_FILE.chmod(0o600)


def refresh_tokens(refresh_token: str) -> dict | None:
    """Refresh OAuth tokens."""
    try:
        response = httpx.post(
            OAUTH_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
    except httpx.RequestError as e:
        console.print(f"[red]Token refresh network error:[/red] {e}")
        return None

    if response.status_code != 200:
        console.print(
            f"[red]Token refresh failed:[/red] {response.status_code} - {response.text}"
        )
        return None

    try:
        data = response.json()
    except json.JSONDecodeError as e:
        console.print(f"[red]Token refresh returned invalid JSON:[/red] {e}")
        return None

    tokens = {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token", refresh_token),
        "expires_at": time.time() + data.get("expires_in", 3600) - 60,
    }
    save_tokens(tokens)
    return tokens


def is_authenticated() -> bool:
    """Check if valid authentication tokens are available."""
    return load_tokens() is not None


def print_auth_status() -> None:
    """Print authentication status to console."""
    tokens = load_tokens()
    if tokens:
        console.print(
            f"[green]Authenticated[/green] (expires {time.ctime(tokens['expires_at'])})"
        )
    else:
        console.print("[yellow]Not authenticated[/yellow]")
        console.print("\n[dim]Make sure Claude Code is authenticated:[/dim]")
        console.print("  claude /login")
        console.print(f"\n[dim]Or manually place tokens at:[/dim] {TOKENS_FILE}")
