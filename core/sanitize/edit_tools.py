"""Edit/Write tool description modifications to recognize semantic search as valid context."""

import re
from typing import Any

# Pattern to match the strict "must Read first" rule in Edit
EDIT_READ_RULE_PATTERN = re.compile(
    r"You must use your `Read` tool at least once in the conversation before editing\. "
    r"This tool will error if you attempt an edit without reading the file\.\s*",
)

EDIT_READ_REPLACEMENT = """Before editing, you need context about the file. This can come from:
- Semantic search results (mcp__semvex__search_code_tool) that include the lines you're editing
- The Read tool for broader file context
Consider reading additional parts of the file if semantic search only showed a small snippet.
Note: A minimal Read (limit=1) satisfies the file access requirement, then use semantic search context for the actual edit.
"""

# Pattern to match the strict "must Read first" rule in Write
WRITE_READ_RULE_PATTERN = re.compile(
    r"If this is an existing file, you MUST use the Read tool first to read the file's contents\. "
    r"This tool will fail if you did not read the file first\.\s*",
)

WRITE_READ_REPLACEMENT = """If this is an existing file, you need context about its contents first. This can come from:
- Semantic search results (mcp__semvex__search_code_tool) showing the file's content
- The Read tool for the full file
For existing files, prefer Edit over Write unless rewriting the entire file.
Note: A minimal Read (limit=1) satisfies the file access requirement, then use semantic search context for understanding.
"""


def relax_read_requirement_inplace(body: dict[str, Any]) -> None:
    """Modify Edit and Write descriptions to accept semantic search as valid context.

    The original descriptions require using Read tool before Edit/Write.
    This relaxes the rule to also accept semantic search results as valid file context.

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

        if name == "Edit" and description:
            tool["description"] = EDIT_READ_RULE_PATTERN.sub(
                EDIT_READ_REPLACEMENT, description
            )

        elif name == "Write" and description:
            tool["description"] = WRITE_READ_RULE_PATTERN.sub(
                WRITE_READ_REPLACEMENT, description
            )
