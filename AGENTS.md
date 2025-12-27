# Repository Guidelines

## Project Structure & Module Organization
- Top-level entry points: `app.py` (FastAPI app factory), `cli.py` (CLI), `auth.py` (auth check).
- API layer: `api/` (`handlers.py`).
- Core logic: `core/` (routing, transforms, headers, config).
- Services: `services/` (targets, routing service, upstream client).
- Auth helper: `auth.py`.
- UI/logging: `ui/` (`dashboard.py`, `logging.py`, `log_utils.py`).
- Request logs are written under `logs/` with subfolders `incoming/`, `zai/`, `anthropic/`.
- Runtime logs are written under `logs/` in `incoming/`, `zai/`, and `antrophic/`.
- `pyproject.toml` defines dependencies, entry points, and tooling settings.

## Build, Test, and Development Commands
- `uv sync` installs dependencies into the local virtualenv.
- `uv run python cli.py` runs the proxy with the default dashboard mode.
- `uv run python cli.py --check` validates auth status (reads Claude Code credentials).
- `uv run python cli.py --config` prints config and token file locations.
- After installing the package, use `claude-code-proxy` instead of `python cli.py`.

## Coding Style & Naming Conventions
- Python 3.11+ with 4-space indentation.
- Use `snake_case` for functions/variables and `PascalCase` for classes.
- Ruff and pyright are configured in `pyproject.toml` (`ruff check .`, `pyright`).
- Keep modules small and single-purpose; add imports at top-level unless deferred imports are required.

## Testing Guidelines
- No tests are present yet; add tests under a `tests/` directory if introducing them.
- Prefer `pytest` with `test_*.py` naming and explicit, minimal fixtures.

## Commit & Pull Request Guidelines
- No Git history is present in this checkout, so commit conventions are not established.
- If using PRs, include: summary, how to run/verify changes, and any config or auth impact.

## Security & Configuration Notes
- Config file: `~/.config/claude-code-proxy/config.json` (includes `zai.api_key`).
- Tokens file: `~/.config/claude-code-proxy/tokens.json`; fallback to `~/.claude/.credentials.json`.
- Do not commit secrets or tokens; use local config files only.
