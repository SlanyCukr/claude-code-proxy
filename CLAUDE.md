# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Claude Code Proxy is a smart HTTP proxy that routes Claude Code API requests between two providers:
- **Main session** → Anthropic (using OAuth from Claude Code)
- **Subagents (Task tool workers)** → z.ai (using API key)

The proxy detects subagent requests via system prompt patterns and routes them to z.ai for cost savings.

## Development Commands

```bash
# Install dependencies
uv sync

# Run proxy with dashboard
uv run python cli.py

# Check auth status
uv run python cli.py --check

# Show config locations
uv run python cli.py --config

# Linting and type checking
uvx ruff check .
uvx pyright
```

## Architecture

### Request Flow
1. FastAPI handler receives request (`api/handlers.py`)
2. `RoutingService.prepare_messages()` processes request
3. `RouteDecider` (`core/router.py`) analyzes system prompt to determine route
4. Request sanitized via `core/sanitize/` package
5. `UpstreamClient` (`services/upstream.py`) proxies to Anthropic or z.ai
6. Response streamed back; activity logged to `logs/`

### Key Modules
- **Entry points**: `cli.py` (CLI + dashboard), `app.py` (FastAPI factory), `auth.py` (OAuth helper)
- **core/router.py**: Pattern matching logic for subagent detection
- **core/config.py**: Configuration using pydantic-settings with nested TOML models
- **core/sanitize/**: Request sanitization package (tools, reminders, system prompts)
- **core/headers.py**: Header building functions for upstream requests
- **services/routing_service.py**: Request routing and preparation
- **services/upstream.py**: HTTP proxy with streaming support
- **ui/dashboard.py**: Real-time CLI dashboard with Rich

### Sanitization Package (`core/sanitize/`)
Modular request sanitization:
- `patterns.py` - Shared regex patterns and constants
- `tools.py` - Tool stripping (remove unwanted tools from requests)
- `task_tool.py` - Task tool description filtering
- `reminders.py` - System reminder transformations
- `system_prompt.py` - System prompt replacement

### Routing Logic
Subagent detection uses markers in `core/router.py`:
- Configurable `subagent_markers` in config.toml
- Configurable `anthropic_markers` for exclusions

### Configuration
Uses pydantic-settings with nested TOML structure. **All values are required** (no defaults):
- **Config file**: `config.toml` in repo root (copy from `config.example.toml`)
- **OAuth tokens**: Read from `~/.claude/.credentials.json`

```toml
[proxy]
port = 8080
debug = true

[anthropic]
base_url = "https://api.anthropic.com"

[zai]
base_url = "https://api.z.ai/api/anthropic"
api_key = "your-key"

[routing]
subagent_markers = ["..."]
anthropic_markers = ["..."]

[limits]
max_body_size = 52428800
timeout = 300.0
max_connections = 100
max_keepalive = 20
subagent_tool_warning = 30
```

### Logging
Runtime logs written to `logs/` with subfolders: `incoming/`, `zai/`, `anthropic/`

## Code Style
- Python 3.11+, 4-space indentation
- `snake_case` for functions/variables, `PascalCase` for classes
- Ruff and pyright configured in `pyproject.toml`
- Use functions over classes for stateless operations
- Prefer in-place modifications with single deep copy at entry

## Testing
No tests yet. If adding tests, use `pytest` with `test_*.py` naming under a `tests/` directory.
