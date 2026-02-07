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

### Request Transformations

All transforms apply in-place on a single deep copy (`core/sanitize/__init__.py`).

**All routed requests:**
- **Tool stripping** (`sanitize/tools.py`) - Strips MCP tools (except `mcp__semvex__*` prefix), removes configured `hidden_tools`. Clears `tool_choice` if it references a stripped tool
- **Task tool rewriting** (`sanitize/task_tool.py`) - Replaces opening text with agent usage guide, strips configured built-in agents, removes examples/instructions, restricts Bash agent description
- **Malware reminder stripping** (`sanitize/reminders.py`) - Removes "consider whether it would be considered malware" system-reminder blocks
- **Plan mode transformation** (`sanitize/reminders.py`) - Rewrites plan mode reminders to reference zai-speckit-plugin agent names
- **Tool result log stripping** (`sanitize/reminders.py`) - Strips `[Tool: ...]` logs from `<output>` blocks
- **Post-env info stripping** (`sanitize/reminders.py`) - Removes model info/git status after `</env>` block
- **System prompt replacement** (`sanitize/system_prompt.py`) - Replaces system prompt from `core/prompts/default_system.txt`, preserving `<env>` block
- **Search tool prioritization** (`sanitize/search_tools.py`) - Adds MCP semantic search warnings to Grep/Glob descriptions
- **Edit/Write relaxation** (`sanitize/edit_tools.py`) - Relaxes "must Read first" to accept semantic search as valid context
- **Bash description replacement** (`sanitize/bash_description.py`) - Replaces verbose Bash description with minimal version

**z.ai-only:**
- **Anthropic feature stripping** (`core/transform.py`) - Removes `metadata`, `cache_control`, noise system-reminders
- **CLAUDE.md stripping** (`sanitize/reminders.py`) - Strips CLAUDE.md context for subagents matching `strip_claude_md_markers`
- **Tool limit warnings** (`core/tool_tracker.py`) - Injects escalating reminders at tool counts: threshold (soft), +10 (strong), +20 (critical)

**Main Anthropic session only:**
- Tool stripping applies (MCP tools + hidden tools removed); subagents routed to Anthropic keep their tools

### Key Modules
- **Entry points**: `cli.py` (CLI + dashboard), `app.py` (FastAPI factory), `auth.py` (OAuth helper)
- **core/router.py**: Pattern matching logic for subagent detection
- **core/config.py**: Configuration using pydantic-settings with nested TOML models
- **core/sanitize/**: Request sanitization package (tools, reminders, system prompts)
- **core/headers.py**: Header building functions for upstream requests
- **services/routing_service.py**: Request routing and preparation
- **services/upstream.py**: HTTP proxy with streaming support
- **core/transform.py**: z.ai-specific transforms (strip metadata, cache_control, noise reminders)
- **core/tool_tracker.py**: Subagent tool usage counting and escalating limit warnings
- **ui/dashboard.py**: Real-time CLI dashboard with Rich

### Sanitization Package (`core/sanitize/`)
Modular request sanitization:
- `patterns.py` - Shared regex patterns and constants
- `tools.py` - Tool stripping (remove unwanted tools from requests)
- `task_tool.py` - Task tool description filtering
- `reminders.py` - System reminder transformations
- `system_prompt.py` - System prompt replacement
- `search_tools.py` - Grep/Glob description modifications (prioritize semantic search)
- `edit_tools.py` - Edit/Write description modifications (relax Read requirement)
- `bash_description.py` - Bash tool description replacement (minimal version)

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
max_connections = 100
max_keepalive = 20
keepalive_expiry = 120.0
connect_timeout = 60.0
pool_timeout = 10.0
keep_alive_timeout = 120
subagent_tool_warning = 30
token_count_timeout = 60.0
message_timeout = 300.0

[sanitize]
hidden_tools = ["NotebookEdit", "WebFetch", "..."]
stripped_agents = ["general-purpose", "Explore", "..."]
strip_claude_md_markers = ["..."]
```

### Logging
Runtime logs written to `logs/` with subfolders: `incoming/`, `zai/`, `anthropic/`

## Gotchas
- MCP tool prefix allowlist (`mcp__semvex__`) is hardcoded in `core/sanitize/patterns.py`, not configurable
- Dashboard silently skips `count_tokens` requests and `haiku` models from display (still logged to disk)
- System prompt replacement looks for `"You are an interactive CLI tool"` marker in system prompt list items - logs warning if not found
- Tool stripping only applies to main Anthropic session - subagents routed to Anthropic keep their tools
- `strip_anthropic_features_inplace` preserves `# claudeMd` reminders as user context, strips other noise reminders
- Event logging endpoint (`/api/event_logging/batch`) silently returns 204 - discards all telemetry

## Code Style
- Python 3.11+, 4-space indentation
- `snake_case` for functions/variables, `PascalCase` for classes
- Ruff and pyright configured in `pyproject.toml`
- Use functions over classes for stateless operations
- Prefer in-place modifications with single deep copy at entry

## Testing
No tests yet. If adding tests, use `pytest` with `test_*.py` naming under a `tests/` directory.
