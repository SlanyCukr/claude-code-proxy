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

# After installing: claude-code-proxy, claude-code-proxy-check

# Linting and type checking
ruff check .
pyright
```

## Architecture

### Request Flow
1. FastAPI handler receives request (`api/handlers.py`)
2. `routing_service.prepare_messages()` processes request
3. `RouteDecider` (`core/router.py`) analyzes system prompt to determine route
4. Request transformed/sanitized for target provider
5. `UpstreamClient` (`services/upstream.py`) proxies to Anthropic or z.ai
6. Response streamed back; activity logged to `logs/`

### Key Modules
- **Entry points**: `cli.py` (CLI + dashboard), `app.py` (FastAPI factory), `auth.py` (OAuth helper)
- **core/router.py**: Pattern matching logic for subagent detection
- **core/config.py**: Pydantic configuration models
- **services/routing_service.py**: Request preparation orchestration
- **services/targets.py**: Upstream target configurations
- **ui/dashboard.py**: Real-time CLI dashboard with Rich

### Routing Logic
Subagent detection uses markers and regex patterns in `core/router.py`:
- `SUBAGENT_PATTERNS`: Patterns like `<role>`, Agent headers, READ-ONLY MODE
- `AIR_MODEL_PATTERNS`: Simple tasks routed to cheaper `glm-4.5-air` model

### Configuration
- **Config**: `config.toml` in repo root (copy from `config.example.toml`, set z.ai API key)
- **Tokens**: OAuth tokens from `~/.claude/.credentials.json`

### Logging
Runtime logs written to `logs/` with subfolders: `incoming/`, `zai/`, `anthropic/`

## Code Style
- Python 3.11+, 4-space indentation
- `snake_case` for functions/variables, `PascalCase` for classes
- Ruff and pyright configured in `pyproject.toml`

## Testing
No tests yet. If adding tests, use `pytest` with `test_*.py` naming under a `tests/` directory.
