"""Track subagent tool usage and inject warnings when threshold exceeded."""

from typing import Any


def count_tool_uses(messages: list[dict[str, Any]]) -> int:
    """Count tool_use blocks in assistant messages."""
    count = 0
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    count += 1
    return count


def _get_warning_message(tool_count: int, threshold: int) -> str | None:
    """Get escalating warning message based on tool count."""
    # Escalating thresholds: soft at base, stronger at base+10, critical at base+20
    critical_threshold = threshold + 20
    strong_threshold = threshold + 10

    if tool_count >= critical_threshold:
        return (
            f"<system-reminder>CRITICAL: You have used {tool_count} tools "
            f"(limit: {critical_threshold}). You MUST stop now and return your "
            "status to the main session immediately. Report what you've completed "
            "and what remains. Do not use any more tools.</system-reminder>"
        )
    elif tool_count >= strong_threshold:
        return (
            f"<system-reminder>WARNING: You have used {tool_count} tools "
            f"(threshold: {strong_threshold}). You should wrap up your current task "
            "now and return your status to the main session. Finish what you're "
            "doing and report back - don't start new work.</system-reminder>"
        )
    elif tool_count >= threshold:
        return (
            f"<system-reminder>Tool usage notice: You have used {tool_count} tools "
            f"(threshold: {threshold}). Consider wrapping up your current task and "
            "returning your status to the main session. It's better to return partial "
            "progress than to continue indefinitely.</system-reminder>"
        )
    return None


def inject_tool_limit_reminder(
    body: dict[str, Any],
    tool_count: int,
    threshold: int,
) -> dict[str, Any]:
    """Inject a system-reminder into the last user message if threshold exceeded."""
    reminder = _get_warning_message(tool_count, threshold)
    if not reminder:
        return body

    messages = body.get("messages", [])
    if not messages:
        return body

    # Find last user message
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            # Create selective shallow copies instead of deepcopy
            body = body.copy()  # shallow copy top-level
            body["messages"] = list(body["messages"])  # copy the list
            body["messages"][i] = dict(body["messages"][i])  # copy only the message being modified
            msg = body["messages"][i]
            content = msg.get("content")

            if isinstance(content, str):
                msg["content"] = f"{reminder}\n\n{content}"
            elif isinstance(content, list):
                # Prepend reminder as text block
                msg["content"] = [{"type": "text", "text": reminder}, *content]
            else:
                # No content, create it
                msg["content"] = reminder

            return body

    return body
