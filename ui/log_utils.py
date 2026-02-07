"""Shared logging utilities.

All disk I/O is offloaded to a background thread pool so log writes
never block the async event loop.
"""

import json
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

LOG_ROOT = Path.cwd() / "logs"
CLI_LOG_FILE = LOG_ROOT / "proxy.log"

_log_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="log-writer")


def clear_logs() -> None:
    """Remove all log files. Called on proxy startup."""
    if LOG_ROOT.exists():
        shutil.rmtree(LOG_ROOT)


def shutdown_log_executor() -> None:
    """Drain pending writes and shut down the log thread pool."""
    _log_executor.shutdown(wait=True)


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
) -> None:
    """Write a single incoming request log entry (non-blocking)."""
    payload = {
        "timestamp": _utc_now(),
        "method": method,
        "path": path,
        "headers": _redact_headers(headers),
        "body": body,
    }
    session_id = _extract_session_id(body)
    folder = LOG_ROOT / "incoming" / session_id if session_id else LOG_ROOT / "incoming"
    _log_executor.submit(_write_json, folder, payload)


def write_zai_log(
    body: dict[str, Any],
    headers: dict[str, str],
    *,
    path: str,
    session_body: dict[str, Any] | None = None,
) -> None:
    """Write a single z.ai request log entry (non-blocking)."""
    payload = {
        "timestamp": _utc_now(),
        "target": "z.ai",
        "path": path,
        "headers": _redact_headers(headers),
        "body": body,
    }
    # Use session_body (original with metadata) for folder extraction if provided
    folder_body = session_body if session_body else body
    session_id = _extract_session_id(folder_body)
    folder = LOG_ROOT / "zai" / session_id if session_id else LOG_ROOT / "zai"
    _log_executor.submit(_write_json, folder, payload)


def write_anthropic_log(
    model: str,
    body: dict[str, Any],
    streaming: bool,
    *,
    path: str,
) -> None:
    """Write a single Anthropic request log entry (non-blocking)."""
    session_id = _extract_session_id(body)
    folder = LOG_ROOT / "anthropic" / session_id if session_id else LOG_ROOT / "anthropic"
    _log_executor.submit(_write_anthropic, folder, model, body, streaming, path)


def _write_anthropic(
    folder: Path, model: str, body: dict[str, Any], streaming: bool, path: str
) -> None:
    """Anthropic log writer (runs in thread pool)."""
    _cleanup_session_folder(folder)
    payload = {
        "timestamp": _utc_now(),
        "target": "Anthropic",
        "model": model,
        "streaming": streaming,
        "path": path,
        "body": body,
    }
    _write_json(folder, payload)


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
    """Append a line to the rolling CLI log file (non-blocking)."""
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    extra_str = " ".join(f"{k}={v}" for k, v in extra.items()) if extra else ""
    line = f"[{timestamp}] {level}: {message}"
    if extra_str:
        line += f" {extra_str}"
    line += "\n"
    _log_executor.submit(_append_cli_log, line)


def _append_cli_log(line: str) -> None:
    """Write a line to the CLI log file (runs in thread pool)."""
    CLI_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CLI_LOG_FILE.open("a") as f:
        f.write(line)


def _write_json(folder: Path, payload: dict[str, Any]) -> Path:
    """Write payload to a unique JSON file in the given folder."""
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    file_path = folder / f"{timestamp}_{uuid4().hex}.json"
    file_path.write_text(json.dumps(payload, indent=2, default=str))
    return file_path


_SAFE_SESSION_ID = re.compile(r"^[a-zA-Z0-9_-]+$")


def _extract_session_id(body: Any) -> str | None:
    """Extract session_id from request body metadata.user_id."""
    if not isinstance(body, dict):
        return None
    user_id = body.get("metadata", {}).get("user_id", "")
    if not isinstance(user_id, str) or "session_" not in user_id:
        return None
    session_id = user_id.split("session_", 1)[-1]
    if not session_id or not _SAFE_SESSION_ID.match(session_id):
        return None
    return session_id

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
