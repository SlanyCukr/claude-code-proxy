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

2. **Set your z.ai API key** in `config.toml`

3. **Run the proxy:**
   ```bash
   uv run python cli.py
   ```

4. **Configure Claude Code:**
   ```bash
   claude config set --global apiBaseUrl http://localhost:8080
   ```

## Configuration

All settings in `config.toml`:

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| `proxy` | `port` | 8080 | Listen port |
| `proxy` | `debug` | true | Debug logging |
| `zai` | `api_key` | - | Your z.ai API key (required) |
| `zai` | `base_url` | api.z.ai/... | z.ai endpoint |
| `anthropic` | `base_url` | api.anthropic.com | Anthropic endpoint |
| `limits` | `timeout` | 300.0 | Request timeout (seconds) |
| `limits` | `max_body_size` | 50MB | Max request body |

## Commands

```bash
uv run python cli.py           # Run with dashboard
uv run python cli.py --check   # Check auth status
uv run python cli.py --config  # Show config path
```

## Architecture

```
Request → FastAPI Handler → Route Decider → Upstream Client → Response
                                ↓
                      Subagent? → z.ai
                      Main?     → Anthropic
```

**Key modules:**
- `cli.py` - Entry point with Rich dashboard
- `core/router.py` - Subagent detection logic
- `core/config.py` - TOML config loading
- `services/upstream.py` - HTTP proxying

## Development

```bash
uv sync          # Install dependencies
ruff check .     # Lint
pyright          # Type check
```

## License

MIT
