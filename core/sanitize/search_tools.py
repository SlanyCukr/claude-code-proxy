"""Search tool description modifications to prioritize semantic search."""

import re
from typing import Any

# Grep: Best performing approach - STOP warning with alternatives
GREP_PRIORITY_PREFIX = """⚠️ STOP: Before using Grep, consider if a better tool exists:

- "Find callers of X" → Use mcp__semvex__find_callers_tool (Grep matches strings, not calls)
- "What does X call" → Use mcp__semvex__find_callees_tool
- "Trace path from A to B" → Use mcp__semvex__get_call_chain_tool
- "Find code related to concept" → Use mcp__semvex__search_code_tool

Grep is ONLY appropriate for:
- Exact literal strings (error messages, specific constants)
- Config values or environment variables
- Comments containing specific text

DO NOT use Grep to verify MCP tool results - MCP tools are authoritative for call relationships.

"""

# Pattern to remove the "ALWAYS use Grep" directive
GREP_ALWAYS_PATTERN = re.compile(
    r"^\s*-\s*ALWAYS use Grep for search tasks\..*?$",
    re.MULTILINE,
)

# Glob: Add semantic search priority note
GLOB_PRIORITY_PREFIX = """For understanding code or finding relevant implementations, prefer semantic search (mcp__semvex__search_code_tool) or Task tool with codebase-explorer agent first.

Use Glob for:
- Finding files by name pattern (e.g., "**/*.test.ts")
- Listing files in a directory structure

"""


def prioritize_semantic_search_inplace(body: dict[str, Any]) -> None:
    """Modify Grep/Glob tool descriptions to prefer MCP semantic search.

    - Grep: Adds warning to use MCP call graph tools instead for code relationships
    - Glob: Adds note to prefer semantic search for code understanding

    Args:
        body: Request body (modified in place).
    """
    tools = body.get("tools")
    if not isinstance(tools, list):
        return

    for tool in tools:
        if not isinstance(tool, dict):
            continue

        name = tool.get("name")
        description = tool.get("description", "")

        if name == "Grep" and description:
            # Remove "ALWAYS use Grep" directive
            description = GREP_ALWAYS_PATTERN.sub("", description)
            # Add priority prefix
            tool["description"] = GREP_PRIORITY_PREFIX + description.lstrip()

        elif name == "Glob" and description:
            # Add priority prefix
            tool["description"] = GLOB_PRIORITY_PREFIX + description.lstrip()
