"""Shared logging utilities."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

LOG_ROOT = Path.cwd() / "logs"
CLI_LOG_FILE = LOG_ROOT / "proxy.log"


def extract_request_info(body: dict[str, Any]) -> tuple[str, list[str]]:
    """Extract prompt and tool names from request body.

    Returns:
        Tuple of (prompt_text, tool_names)
    """
    prompt = ""
    messages = body.get("messages", [])
    if messages:
        # Find first user message (contains initial prompt for subagents)
        first_user_msg = next(
            (m for m in messages if m.get("role") == "user"),
            None,
        )
        if first_user_msg:
            content = first_user_msg.get("content", "")
            if isinstance(content, list):
                texts = [
                    b.get("text", "")
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                ]
                content = " ".join(texts)
            prompt = content.replace("\n", " ").strip() if content else ""

    tools = body.get("tools", [])
    tool_names = [t.get("name", "?") for t in tools if isinstance(t, dict)]

    return prompt, tool_names


def write_incoming_log(
    method: str,
    path: str,
    headers: dict[str, str],
    body: Any,
    *,
    log_root: Path = LOG_ROOT,
) -> Path:
    """Write a single incoming request log entry."""
    payload = {
        "timestamp": _utc_now(),
        "method": method,
        "path": path,
        "headers": _redact_headers(headers),
        "body": body,
    }
    return _write_json(_session_folder(log_root / "incoming", body), payload)


def write_zai_log(
    body: dict[str, Any],
    headers: dict[str, str],
    *,
    path: str,
    session_body: dict[str, Any] | None = None,
    log_root: Path = LOG_ROOT,
) -> Path:
    """Write a single z.ai request log entry."""
    payload = {
        "timestamp": _utc_now(),
        "target": "z.ai",
        "path": path,
        "headers": _redact_headers(headers),
        "body": body,
    }
    # Use session_body (original with metadata) for folder extraction if provided
    folder_body = session_body if session_body else body
    return _write_json(_session_folder(log_root / "zai", folder_body), payload)


def write_anthropic_log(
    model: str,
    body: dict[str, Any],
    streaming: bool,
    *,
    path: str,
    log_root: Path = LOG_ROOT,
) -> Path:
    """Write a single Anthropic request log entry."""
    folder = _session_folder(log_root / "anthropic", body)

    # Cleanup old logs in session folder (keep only latest)
    _cleanup_session_folder(folder)

    payload = {
        "timestamp": _utc_now(),
        "target": "Anthropic",
        "model": model,
        "streaming": streaming,
        "path": path,
        "body": body,
    }
    return _write_json(folder, payload)


def _cleanup_session_folder(folder: Path) -> int:
    """Delete all but the most recent log file in a session folder."""
    if not folder.exists():
        return 0

    files = sorted(folder.glob("*.json"))
    if len(files) <= 1:
        return 0

    deleted = 0
    # Delete all but the last file (most recent by filename timestamp)
    for old_file in files[:-1]:
        try:
            old_file.unlink()
            deleted += 1
        except OSError:
            pass
    return deleted


def write_cli_log(
    level: str,
    message: str,
    **extra: Any,
) -> None:
    """Append a line to the rolling CLI log file."""
    CLI_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    extra_str = " ".join(f"{k}={v}" for k, v in extra.items()) if extra else ""
    line = f"[{timestamp}] {level}: {message}"
    if extra_str:
        line += f" {extra_str}"
    line += "\n"
    with CLI_LOG_FILE.open("a") as f:
        f.write(line)


def _write_json(folder: Path, payload: dict[str, Any]) -> Path:
    """Write payload to a unique JSON file in the given folder."""
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    file_path = folder / f"{timestamp}_{uuid4().hex}.json"
    file_path.write_text(json.dumps(payload, indent=2, default=str))
    return file_path


def _session_folder(base: Path, body: Any) -> Path:
    session_id = _extract_session_id(body)
    if session_id:
        return base / session_id
    return base


def _extract_session_id(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    metadata = body.get("metadata")
    if not isinstance(metadata, dict):
        return None
    user_id = metadata.get("user_id")
    if not isinstance(user_id, str):
        return None
    marker = "session_"
    if marker not in user_id:
        return None
    session_id = user_id.split(marker, 1)[-1]
    return session_id or None

def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Redact sensitive headers."""
    redacted = {}
    for key, value in headers.items():
        if "key" in key.lower() or "authorization" in key.lower():
            redacted[key] = _mask(value)
        else:
            redacted[key] = value
    return redacted


def _mask(value: str) -> str:
    if len(value) <= 10:
        return "***"
    return value[:6] + "..." + value[-4:]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
