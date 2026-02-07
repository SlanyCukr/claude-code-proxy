# Claude Code Proxy

Smart HTTP proxy that routes Claude Code API requests between Anthropic (main session, OAuth) and z.ai (subagents, API key) - with request sanitization and a real-time dashboard.

## What It Does

- **Routes requests** - Main session goes to Anthropic; Task tool subagents go to z.ai for cost savings
- **Sanitizes requests** - Strips/rewrites tools, system prompts, reminders, and descriptions to optimize subagent behavior
- **Real-time dashboard** - Rich CLI dashboard showing live request routing, token usage, and activity

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- z.ai API key
- Claude Code with active OAuth session (`~/.claude/.credentials.json`)

### Install

```bash
git clone <repo-url>
cd claude-code-proxy
uv sync
```

### Configure

```bash
cp config.example.toml config.toml
# Edit config.toml - set your z.ai API key at minimum
```

See `config.example.toml` for all available settings.

### Run

```bash
uv run python cli.py
```

Other commands:

```bash
uv run python cli.py --check   # Check OAuth auth status
uv run python cli.py --config  # Show config file locations
```

## Using with Claude Code

Point Claude Code at the proxy by setting the base URL:

```bash
export ANTHROPIC_BASE_URL=http://localhost:8080
```

Then use Claude Code normally. The proxy transparently intercepts requests and routes them based on system prompt analysis.

## Configuration

All configuration lives in `config.toml` (copy from `config.example.toml`). Key sections:

| Section | Purpose |
|---------|---------|
| `[proxy]` | Port, debug mode |
| `[anthropic]` | Anthropic API base URL |
| `[zai]` | z.ai base URL and API key |
| `[routing]` | Subagent detection markers, Anthropic routing markers |
| `[limits]` | Connection pools, timeouts, tool warning thresholds |
| `[sanitize]` | Hidden tools, stripped agents, CLAUDE.md stripping markers |

## Architecture

```
Claude Code  -->  FastAPI proxy  -->  Anthropic (main session, OAuth)
                      |
                      +---------->  z.ai (subagents, API key)
```

1. Request arrives at FastAPI handler
2. `RouteDecider` analyzes system prompt for subagent markers
3. Request sanitized (tool stripping, prompt replacement, description rewrites)
4. Proxied upstream with streaming response
5. Activity logged and displayed on dashboard

For detailed architecture, transforms, and module reference, see [CLAUDE.md](./CLAUDE.md).

## License

[MIT](./LICENSE)
