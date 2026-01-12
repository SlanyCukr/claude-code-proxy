# Claude Code Proxy

Route Claude Code API requests between providers for cost optimization.

## How It Works

```
Claude Code  ──►  Proxy  ──┬──►  Anthropic (main session)
                          └──►  z.ai (subagents)
```

- **Main session** requests go to Anthropic using Claude Code's OAuth
- **Subagent** requests (Task tool workers) go to z.ai using API key

Detection is automatic via system prompt patterns.

## Quick Start

1. **Copy config template:**
   ```bash
   cp config.example.toml config.toml
   ```

2. **Set your z.ai API key** in `config.toml` (required)

3. **Run the proxy:**
   ```bash
   uv run python cli.py
   ```

4. **Configure Claude Code:**
   ```bash
   claude config set --global apiBaseUrl http://localhost:8080
   ```

## Configuration

All settings in `config.toml` are **required** (no defaults). Uses pydantic-settings with nested TOML:

| Section | Key | Description |
|---------|-----|-------------|
| `proxy` | `port` | Listen port |
| `proxy` | `debug` | Debug logging |
| `zai` | `api_key` | Your z.ai API key |
| `zai` | `base_url` | z.ai endpoint |
| `anthropic` | `base_url` | Anthropic endpoint |
| `routing` | `subagent_markers` | Patterns identifying subagents |
| `routing` | `anthropic_markers` | Patterns forcing Anthropic |
| `limits` | `timeout` | Request timeout (seconds) |
| `limits` | `max_body_size` | Max request body (bytes) |
| `limits` | `max_connections` | Max HTTP connections |
| `limits` | `max_keepalive` | Max keepalive connections |
| `limits` | `subagent_tool_warning` | Warn after N tool uses (0 to disable) |

## Commands

```bash
uv run python cli.py           # Run with dashboard
uv run python cli.py --check   # Check auth status
uv run python cli.py --config  # Show config path
```

## Architecture

```
Request → FastAPI Handler → Route Decider → Sanitize → Upstream Client → Response
                                ↓
                      Subagent? → z.ai
                      Main?     → Anthropic
```

**Key modules:**
- `cli.py` - Entry point with Rich dashboard
- `core/router.py` - Subagent detection logic
- `core/config.py` - pydantic-settings TOML config
- `core/sanitize/` - Request sanitization package
- `services/upstream.py` - HTTP proxying

## Development

```bash
uv sync            # Install dependencies
uvx ruff check .   # Lint
uvx pyright        # Type check
```

## License

MIT
