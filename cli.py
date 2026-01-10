"""CLI entry point for claude-code-proxy."""

import sys
from datetime import datetime

from rich.console import Console

from app import create_app
from auth import TOKENS_FILE, check_auth, load_tokens
from core.config import CONFIG_FILE, load_config
from ui.dashboard import Dashboard
from ui.log_utils import write_cli_log

console = Console()


def main():
    """Main CLI entry point."""
    config = load_config()

    # Handle CLI arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg in ("--check", "--auth"):
            check_auth()
            return

        if arg == "--config":
            console.print(f"[bold]Config:[/bold] {CONFIG_FILE}")
            console.print(f"[bold]Tokens:[/bold] {TOKENS_FILE}")
            return

        if arg in ("--help", "-h"):
            _print_help()
            return

    # Validate z.ai API key (required for all server modes)
    if not config.zai_api_key:
        console.print("[red][ERROR][/red] z.ai API key not configured!")
        console.print(f"[dim]Edit {CONFIG_FILE} and set zai.api_key[/dim]")
        sys.exit(1)

    # Check auth status
    tokens = load_tokens()
    if not tokens:
        console.print("[yellow]Warning:[/yellow] Not authenticated (run claude /login)")

    # Start dashboard and server
    dashboard = Dashboard(config)

    import uvicorn

    app = create_app(config, dashboard)

    # Run with dashboard
    uvicorn_config = uvicorn.Config(
        app, host="0.0.0.0", port=config.port, log_level="warning"
    )
    server = uvicorn.Server(uvicorn_config)

    dashboard.start()
    start_time = datetime.now()
    write_cli_log("STARTUP", "Proxy started", port=config.port)
    try:
        server.run()
    finally:
        duration = datetime.now() - start_time
        write_cli_log("SHUTDOWN", "Proxy stopped", duration=str(duration))
        dashboard.stop()


def _print_help():
    """Print help message."""
    help_text = """
[bold cyan]Claude Code Proxy[/bold cyan]

Routes main Claude session to Anthropic (via OAuth), subagents to z.ai.

[bold]Usage:[/bold]
    claude-code-proxy              Start with live dashboard
    claude-code-proxy --check      Check auth status
    claude-code-proxy --config     Show config locations
    claude-code-proxy --help       Show this help

[bold]Authentication:[/bold]
    Uses Claude Code's OAuth tokens from ~/.claude/.credentials.json
    Run `claude /login` if not authenticated.
"""
    console.print(help_text)


if __name__ == "__main__":
    main()
