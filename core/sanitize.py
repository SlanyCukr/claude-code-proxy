"""Request sanitization for upstream routing."""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

DEFAULT_STRIPPED_TOOLS = {"NotebookEdit", "WebFetch", "WebSearch"}

DEFAULT_STRIPPED_AGENTS = {
    "general-purpose",
    "statusline-setup",
    "Explore",
    "Plan",
    "claude-code-guide",
}
MCP_TOOL_PREFIX = "mcp__"
MCP_TOOL_ALLOWLIST = {"mcp__codex__codex", "mcp__codex__codex-reply"}

# Pre-compiled regex patterns for tool result stripping
_TOOL_RESULT_OUTPUT_WRAPPER = re.compile(r"<output>\s*(.*?)\s*</output>", re.DOTALL)
_TOOL_CALL_LOG_PATTERN = re.compile(r"^\[Tool: \w+\] \{.*?\}\n?", re.MULTILINE)
_RESULT_SEPARATOR = "--- RESULT ---"

# Pre-compiled regex patterns
_OLD_OPENING_PATTERN = re.compile(
    r"Launch a new agent to handle complex, multi-step tasks autonomously\. "
    r"\n\nThe Task tool launches specialized agents \(subprocesses\) that "
    r"autonomously handle complex tasks\. Each agent type has specific "
    r"capabilities and tools available to it\."
)
_CONTEXT_PATTERN = re.compile(
    r"- Agents with \"access to current context\".*?understand the context\.\n",
    re.DOTALL,
)
_EXAMPLE_PATTERN = re.compile(r"\n*Example usage:.*$", re.DOTALL)
_MALWARE_REMINDER_PATTERN = re.compile(
    r"<system-reminder>\s*Whenever you read a file, you should consider whether "
    r"it would be considered malware\..*?</system-reminder>\s*",
    re.DOTALL,
)


def _agent_pattern(agent: str) -> re.Pattern[str]:
    return re.compile(rf"- {re.escape(agent)}:.*?\(Tools:.*?\)\n", re.DOTALL)


_AGENT_PATTERNS = {agent: _agent_pattern(agent) for agent in DEFAULT_STRIPPED_AGENTS}

# Load system prompt from file
_PROMPT_FILE = Path(__file__).parent / "prompts" / "default_system.txt"
if not _PROMPT_FILE.exists():
    raise SystemExit(f"System prompt not found: {_PROMPT_FILE}")
DEFAULT_SYSTEM_PROMPT = _PROMPT_FILE.read_text()


def _contains_malware_marker(content: Any) -> bool:
    """Check if content contains the malware reminder marker."""
    marker = "you should consider whether it would be considered malware"
    if isinstance(content, str):
        return marker in content
    if isinstance(content, list):
        return any(
            isinstance(b, dict)
            and b.get("type") == "text"
            and isinstance(b.get("text"), str)
            and marker in b["text"]
            for b in content
        )
    return False


def _has_tool_call_logs(content: Any) -> bool:
    """Check if content contains verbose tool call logs in <output> section."""
    if isinstance(content, str):
        return "<output>" in content and "[Tool: " in content
    return False


def _strip_tool_call_logs(content: str) -> str:
    """Strip tool call logs from <output> section, keeping metadata and result."""
    output_match = _TOOL_RESULT_OUTPUT_WRAPPER.search(content)
    if not output_match:
        return content

    inner = output_match.group(1)

    # Find the actual result after separator
    if _RESULT_SEPARATOR in inner:
        result_idx = inner.find(_RESULT_SEPARATOR)
        cleaned_inner = inner[result_idx:].strip()  # Keep separator + result
    else:
        # No separator - strip tool call logs
        cleaned_inner = _TOOL_CALL_LOG_PATTERN.sub("", inner).strip()

    # Replace original <output> section with cleaned version
    return content.replace(
        output_match.group(0), f"<output>\n{cleaned_inner}\n</output>"
    )


class RequestSanitizer:
    """Strip unwanted request content before routing upstream."""

    def __init__(
        self,
        *,
        stripped_tools: set[str] | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self._stripped_tools = stripped_tools or DEFAULT_STRIPPED_TOOLS
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    def sanitize(self, body: dict[str, Any], *, strip_mcp: bool = True) -> dict[str, Any]:
        """Remove unwanted tools and replace the system prompt."""
        body = self._strip_tools(body, strip_mcp=strip_mcp)
        body = self._filter_task_tool(body)
        body = self._strip_system_reminders(body)
        body = self._strip_tool_result_logs(body)
        return self._replace_system_prompt(body)

    def _strip_tools(self, body: dict[str, Any], *, strip_mcp: bool = True) -> dict[str, Any]:
        tools = body.get("tools")
        if not isinstance(tools, list):
            return body

        body = copy.deepcopy(body)
        body["tools"] = [
            tool for tool in tools if not self._should_strip_tool(tool, strip_mcp=strip_mcp)
        ]

        tool_choice = body.get("tool_choice")
        if isinstance(tool_choice, dict) and tool_choice.get("name") in self._stripped_tools:
            body.pop("tool_choice", None)

        return body

    def _should_strip_tool(self, tool: Any, *, strip_mcp: bool = True) -> bool:
        if not isinstance(tool, dict):
            return False
        name = tool.get("name")
        if not isinstance(name, str):
            return False
        if name in self._stripped_tools:
            return True
        if strip_mcp and name.startswith(MCP_TOOL_PREFIX) and name not in MCP_TOOL_ALLOWLIST:
            return True
        return False

    def _filter_task_tool(self, body: dict[str, Any]) -> dict[str, Any]:
        """Remove default agent descriptions and unwanted sections from Task tool."""
        tools = body.get("tools")
        if not isinstance(tools, list):
            return body

        for tool in tools:
            if not isinstance(tool, dict) or tool.get("name") != "Task":
                continue
            description = tool.get("description", "")
            if not description:
                continue
            original_description = description

            # Replace opening text
            new_opening = (
                "Delegate work to agents that run in isolation. "
                "Preserves main session context while agents handle focused tasks.\n\n"
                "**How to use effectively:**\n"
                "- Give ONE small, focused task per agent - broad tasks lead to incomplete work\n"
                "- Agents start fresh with no prior context - provide everything they need:\n"
                "  - File paths to read (specs, docs, code to reference/modify)\n"
                "  - Exact commands if they need to run builds, tests, docker, pre-commit hooks\n"
                "  - Write a context file (e.g., /tmp/task-context.md) and pass its path if context is complex\n"
                "- Don't paste file contents in the prompt - give paths and let agents read them\n"
                "- If unsure about command structure, verify it in main session first, then pass exact commands to agent"
            )
            description = _OLD_OPENING_PATTERN.sub(new_opening, description)

            # Filter out default agent entries
            for agent in DEFAULT_STRIPPED_AGENTS:
                description = _AGENT_PATTERNS[agent].sub("", description)

            # Strip instruction and example sections
            description = _CONTEXT_PATTERN.sub("", description)
            description = _EXAMPLE_PATTERN.sub("", description)

            if description != original_description:
                body = copy.deepcopy(body)
                for t in body["tools"]:
                    if isinstance(t, dict) and t.get("name") == "Task":
                        t["description"] = description
                        break
            break

        return body

    def _strip_system_reminders(self, body: dict[str, Any]) -> dict[str, Any]:
        """Strip specific <system-reminder> blocks from message content."""
        messages = body.get("messages")
        if not isinstance(messages, list):
            return body

        if not any(_contains_malware_marker(msg.get("content")) for msg in messages):
            return body

        body = copy.deepcopy(body)
        for msg in body["messages"]:
            content = msg.get("content")
            if isinstance(content, str):
                msg["content"] = _MALWARE_REMINDER_PATTERN.sub("", content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        if isinstance(text, str):
                            block["text"] = _MALWARE_REMINDER_PATTERN.sub("", text)

        return body

    def _strip_tool_result_logs(self, body: dict[str, Any]) -> dict[str, Any]:
        """Strip verbose tool call logs from tool_result content blocks."""
        messages = body.get("messages")
        if not isinstance(messages, list):
            return body

        # Check if any tool_result has tool call logs
        needs_update = False
        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_result"
                    and _has_tool_call_logs(block.get("content"))
                ):
                    needs_update = True
                    break
            if needs_update:
                break

        if not needs_update:
            return body

        body = copy.deepcopy(body)
        for msg in body["messages"]:
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    raw_content = block.get("content")
                    if isinstance(raw_content, str) and _has_tool_call_logs(
                        raw_content
                    ):
                        block["content"] = _strip_tool_call_logs(raw_content)

        return body

    def _replace_system_prompt(self, body: dict[str, Any]) -> dict[str, Any]:
        if "system" not in body:
            return body

        original_system = body.get("system")
        original_text = self._extract_system_text(original_system)
        system_prompt = self._merge_env(self._system_prompt, original_text)
        normalized = self._normalize_system(system_prompt, original_system)

        if original_system == normalized:
            return body

        body = copy.deepcopy(body)
        body["system"] = normalized
        return body

    @staticmethod
    def _normalize_system(system_prompt: str, original_system: Any) -> Any:
        if isinstance(original_system, list):
            updated = []
            replaced = False
            for item in original_system:
                if (
                    isinstance(item, dict)
                    and isinstance(item.get("text"), str)
                    and "You are an interactive CLI tool" in item["text"]
                ):
                    new_item = dict(item)
                    new_item["text"] = system_prompt
                    updated.append(new_item)
                    replaced = True
                else:
                    updated.append(item)
            return updated if replaced else original_system

        if isinstance(original_system, dict):
            return {"type": "text", "text": system_prompt}

        return system_prompt

    @staticmethod
    def _extract_system_text(system: Any) -> str:
        if isinstance(system, list):
            parts: list[str] = []
            for item in system:
                if isinstance(item, dict):
                    parts.append(str(item.get("text", "")))
                else:
                    parts.append(str(item))
            return " ".join(parts)
        return str(system) if system else ""

    @staticmethod
    def _extract_env_block(text: str) -> str | None:
        if not text:
            return None
        start = text.find("<env>")
        if start == -1:
            return None
        end = text.find("</env>", start)
        if end == -1:
            return None
        return text[start : end + len("</env>")]

    @classmethod
    def _merge_env(cls, base_prompt: str, original_system: str) -> str:
        original_env = cls._extract_env_block(original_system)
        if not original_env:
            return base_prompt
        base_env = cls._extract_env_block(base_prompt)
        if not base_env:
            return base_prompt
        return base_prompt.replace(base_env, original_env, 1)
