"""Shared regex patterns and constants for request sanitization."""

import re

# MCP tool handling
MCP_TOOL_PREFIX = "mcp__"
MCP_TOOL_ALLOWLIST: set[str] = set()  # Exact tool names to allow
MCP_TOOL_PREFIX_ALLOWLIST = {"mcp__semvex__"}  # Prefixes to allow (all tools from these servers)

# Tool result stripping patterns
TOOL_RESULT_OUTPUT_WRAPPER = re.compile(r"<output>\n\s*(.*?)\s*\n</output>", re.DOTALL)
TOOL_CALL_LOG_PATTERN = re.compile(r"^\[Tool: \w+\] \{.*?\}\n?", re.MULTILINE)
RESULT_SEPARATOR = "--- RESULT ---"

# Task tool description patterns
OLD_OPENING_PATTERN = re.compile(
    r"Launch a new agent to handle complex, multi-step tasks autonomously\. "
    r"\n\nThe Task tool launches specialized agents \(subprocesses\) that "
    r"autonomously handle complex tasks\. Each agent type has specific "
    r"capabilities and tools available to it\."
)
CONTEXT_PATTERN = re.compile(
    r"- Agents with \"access to current context\".*?understand the context\.\n",
    re.DOTALL,
)
EXAMPLE_PATTERN = re.compile(r"\n*Example usage:.*$", re.DOTALL)
# Strip "(Tools: ...)" from agent descriptions in Task tool
AGENT_TOOLS_PATTERN = re.compile(r" \(Tools: [^)]+\)")

# Bash agent description replacement - restrict to git/system commands only
BASH_AGENT_OLD_DESC = re.compile(
    r"- Bash: Command execution specialist for running bash commands\. "
    r"Use this for git operations, command execution, and other terminal tasks\."
)
BASH_AGENT_NEW_DESC = (
    "- Bash: Git and system commands ONLY. "
    "Use for: git operations, docker, npm/pip install, running tests/builds. "
    "NEVER for: reading files, searching code, exploring codebase (use codebase-explorer instead)."
)

# Noise patterns in system-reminders (not user instructions, safe to strip)
NOISE_REMINDER_MARKERS = [
    "consider whether it would be considered malware",
    "SessionStart:",
    "UserPromptSubmit:",
]

# Malware reminder pattern
MALWARE_REMINDER_PATTERN = re.compile(
    r"<system-reminder>\s*Whenever you read a file, you should consider whether "
    r"it would be considered malware\..*?</system-reminder>\s*",
    re.DOTALL,
)

# CLAUDE.md context reminder pattern (injected by Claude Code for all requests)
CLAUDE_MD_REMINDER_PATTERN = re.compile(
    r"<system-reminder>\s*As you answer the user's questions, you can use the "
    r"following context:\s*# claudeMd.*?</system-reminder>\s*",
    re.DOTALL,
)

# Strip verbose info after </env> block for subagents (model info, git status, etc.)
POST_ENV_INFO_PATTERN = re.compile(
    r"</env>\n.*$",
    re.DOTALL,
)
POST_ENV_REPLACEMENT = "</env>"

# Plan mode reminder transformations
PLAN_MODE_REPLACEMENTS = [
    (
        "In this phase you should only use the Explore subagent type.",
        "In this phase you should use the zai-speckit-plugin:codebase-explorer subagent type. "
        "For investigating failures or debugging issues, use zai-speckit-plugin:root-cause-agent instead.",
    ),
    (
        "Launch up to 3 Explore agents IN PARALLEL",
        "Launch up to 3 zai-speckit-plugin:codebase-explorer agents IN PARALLEL",
    ),
    (
        "3. After exploring the code, use the AskUserQuestion tool to clarify ambiguities in the user request up front.",
        "3. After exploring the code, use the AskUserQuestion tool to clarify ambiguities in the user request up front.\n\n"
        "**Research agents available:**\n"
        "- **zai-speckit-plugin:context7-docs**: Look up library documentation (FastAPI, React, etc.)\n"
        "- **zai-speckit-plugin:web-research**: Search for best practices, tutorials, error codes, or API docs not in Context7. "
        "Also useful when investigating issues to look up error messages or stack traces.",
    ),
    # Plan agent replacements
    (
        "Launch Plan agent(s) to design the implementation",
        "Launch zai-speckit-plugin:architect agent(s) to design the implementation",
    ),
    (
        "Launch at least 1 Plan agent for most tasks",
        "Launch at least 1 zai-speckit-plugin:architect agent for most tasks",
    ),
]


def build_agent_pattern(agent: str) -> re.Pattern[str]:
    """Build regex pattern for stripping an agent from Task tool description.

    Agent patterns match format: "- AgentName: description (Tools: ...)\n"
    Note: re.escape handles special chars in agent names (like "general-purpose")
    """
    return re.compile(rf"- {re.escape(agent)}:.*?\(Tools:.*?\)\n", re.DOTALL)

# New Task tool opening text
NEW_TASK_OPENING = (
    "Delegate work to agents that run in isolation. "
    "Preserves main session context while agents handle focused tasks.\n\n"
    "**How to use effectively:**\n"
    "- Give focused, precise, scoped task per agent - broad tasks lead to incomplete work\n"
    "- Agents start fresh with no prior context - provide everything they need:\n"
    "  - File paths to read (specs, docs, code to reference/modify)\n"
    "  - Exact commands if they need to run builds, tests, docker, pre-commit hooks\n"
    "  - Write a context file (e.g., /tmp/task-context.md) and pass its path if context is complex\n"
    "- Don't paste file contents in the prompt - give paths and let agents read them\n"
    "- If unsure about command structure, verify it in main session first, then pass exact commands to agent\n\n"
    "**Pass file paths, not descriptions:**\n"
    "- Files to modify: `src/api/users.py, src/models/user.py`\n"
    "- Reference code: `src/utils/auth.py (see token handling)`\n"
    "- Previous agent outputs: `/tmp/zai-speckit/toon/abc123.toon, /tmp/zai-speckit/toon/def456.toon`\n"
    "- Plan file: `/tmp/plan.md (task 3)`\n"
    "- Specs/config: `docs/api-spec.md, pyproject.toml`"
)
