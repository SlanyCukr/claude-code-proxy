"""Real-time CLI dashboard for proxy monitoring."""

from datetime import datetime
from threading import Lock
from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.config import Config
from ui.log_utils import extract_request_info, write_anthropic_log, write_cli_log, write_zai_log

console = Console()


class RequestInfo:
    """Info about a single request."""

    def __init__(self, model: str, prompt: str, tools: list[str], timestamp: datetime):
        self.model = model
        self.prompt = prompt[:60] + "..." if len(prompt) > 60 else prompt
        self.tools = tools[:4]  # Keep first 4 tools
        self.tools_count = len(tools)
        self.timestamp = timestamp


class Dashboard:
    """Real-time dashboard showing main session and subagents."""

    def __init__(self, config: Config):
        self.config = config
        self._lock = Lock()
        self._main_session: RequestInfo | None = None
        self._subagents: list[RequestInfo] = []
        self._max_subagents = 6
        self._request_count = {"anthropic": 0, "zai": 0}
        self._errors: list[str] = []
        self._live: Live | None = None

    def start(self) -> "Dashboard":
        """Start the live dashboard."""
        self._live = Live(
            self._build_layout(),
            console=console,
            refresh_per_second=4,
            screen=False,
        )
        self._live.start()
        return self

    def stop(self) -> None:
        """Stop the live dashboard."""
        if self._live:
            self._live.stop()

    def log_anthropic(
        self,
        model: str,
        body: dict[str, Any],
        streaming: bool = False,
        *,
        path: str,
    ) -> None:
        """Log a request routed to Anthropic (main session)."""
        with self._lock:
            self._request_count["anthropic"] += 1
            prompt, tools = extract_request_info(body)
            self._main_session = RequestInfo(
                model=model + (" (stream)" if streaming else ""),
                prompt=prompt,
                tools=tools,
                timestamp=datetime.now(),
            )
            self._refresh()

            write_anthropic_log(model, body, streaming, path=path)
            prompt_preview = prompt[:200] if prompt else ""
            write_cli_log("ANTHROPIC", prompt_preview, model=model)

    def log_zai(
        self,
        model: str,
        body: dict[str, Any],
        headers: dict[str, str],
        *,
        path: str,
        session_body: dict[str, Any] | None = None,
    ) -> None:
        """Log a request routed to z.ai (subagent)."""
        with self._lock:
            self._request_count["zai"] += 1
            prompt, tools = extract_request_info(body)
            info = RequestInfo(
                model=model,
                prompt=prompt,
                tools=tools,
                timestamp=datetime.now(),
            )
            self._subagents.insert(0, info)
            self._subagents = self._subagents[: self._max_subagents]

            write_zai_log(body, headers, path=path, session_body=session_body)
            prompt_preview = prompt[:200] if prompt else ""
            write_cli_log("ZAI", prompt_preview, model=model)

            self._refresh()

    def log_error(self, route: str, status: int, message: str) -> None:
        """Log an error."""
        with self._lock:
            truncated = message[:50] + "..." if len(message) > 50 else message
            self._errors.insert(0, f"{route} {status}: {truncated}")
            self._errors = self._errors[:3]
            self._refresh()
            write_cli_log("ERROR", message[:200], route=route, status=status)

    def _refresh(self) -> None:
        """Refresh the display."""
        if self._live:
            self._live.update(self._build_layout())

    def _build_layout(self) -> Layout:
        """Build the dashboard layout."""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=4),
        )

        layout["body"].split_row(
            Layout(name="main", ratio=1),
            Layout(name="subagents", ratio=2),
        )

        # Header
        layout["header"].update(self._build_header())

        # Main session panel
        layout["main"].update(self._build_main_panel())

        # Subagents panel
        layout["subagents"].update(self._build_subagents_panel())

        # Footer with errors
        layout["footer"].update(self._build_footer())

        return layout

    def _build_header(self) -> Panel:
        """Build header with stats."""
        stats = Text()
        stats.append("Claude Code Proxy", style="bold cyan")
        stats.append("  |  ")
        stats.append(f"Anthropic: {self._request_count['anthropic']}", style="blue")
        stats.append("  |  ")
        stats.append(f"z.ai: {self._request_count['zai']}", style="magenta")
        stats.append("  |  ")
        stats.append(f"Port: {self.config.proxy.port}", style="dim")

        return Panel(stats, style="cyan")

    def _build_main_panel(self) -> Panel:
        """Build main session panel."""
        if self._main_session:
            content = Table.grid(padding=(0, 1))
            content.add_column()
            content.add_column()

            content.add_row("[bold]Model:[/bold]", self._main_session.model)
            content.add_row("[bold]Prompt:[/bold]", self._main_session.prompt or "[dim]—[/dim]")

            if self._main_session.tools:
                tools_str = ", ".join(self._main_session.tools)
                if self._main_session.tools_count > 4:
                    tools_str += f" (+{self._main_session.tools_count - 4})"
                content.add_row("[bold]Tools:[/bold]", tools_str)

            content.add_row(
                "[bold]Time:[/bold]",
                self._main_session.timestamp.strftime("%H:%M:%S"),
            )
        else:
            content = Text("Waiting for requests...", style="dim")

        return Panel(content, title="[blue]Main Session[/blue]", border_style="blue")

    def _build_subagents_panel(self) -> Panel:
        """Build subagents panel."""
        if self._subagents:
            table = Table(show_header=True, header_style="bold", expand=True, box=None)
            table.add_column("Time", style="dim", width=8)
            table.add_column("Model", width=20)
            table.add_column("Prompt", ratio=2)
            table.add_column("Tools", ratio=1)

            for sa in self._subagents:
                tools_str = ", ".join(sa.tools[:3])
                if sa.tools_count > 3:
                    tools_str += f" +{sa.tools_count - 3}"

                table.add_row(
                    sa.timestamp.strftime("%H:%M:%S"),
                    sa.model[:20],
                    sa.prompt[:40] + "..." if len(sa.prompt) > 40 else sa.prompt,
                    tools_str,
                )

            content = table
        else:
            content = Text("No subagent requests yet...", style="dim")

        return Panel(
            content, title="[magenta]Subagents (z.ai)[/magenta]", border_style="magenta"
        )

    def _build_footer(self) -> Panel:
        """Build footer with errors and help."""
        if self._errors:
            error_text = Text()
            for err in self._errors:
                error_text.append("! ", style="red bold")
                error_text.append(err + "\n", style="red")
            content = error_text
        else:
            content = Text(
                f"Set ANTHROPIC_BASE_URL=http://localhost:{self.config.proxy.port} to use",
                style="dim",
            )

        return Panel(content, title="[dim]Status[/dim]", border_style="dim")
