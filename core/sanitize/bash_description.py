"""Bash tool description sanitization for subagents."""

from typing import Any

MINIMAL_BASH_DESCRIPTION = """Executes a bash command with optional timeout.

Avoid using Bash for code search — use the Grep tool (for grep, rg) or Glob tool (for find, fd) instead.
Bash is appropriate for: builds, tests, git, package management, data processing (jq, awk), and piping command output.

Parameters:
- command (required): The command to execute
- timeout (optional): Timeout in milliseconds (max 600000, default 120000)
- description (optional): Short description of what command does

Notes:
- Quote paths with spaces: cd "/path/with spaces"
- Chain commands with && for sequential execution
- Use absolute paths when possible
- Prefer specialized tools: Read (not cat), Edit (not sed)
- NEVER run destructive git commands (push --force, reset --hard) without explicit user request
"""

# Only mention run_in_background if TaskOutput is available
BASH_BACKGROUND_SUFFIX = """
- run_in_background (optional): Set true to run in background. Use TaskOutput to read output later.
"""


MINIMAL_DESCRIPTION_PARAM = "Short description of what command does"


def strip_bash_description_inplace(body: dict[str, Any]) -> None:
    """Replace verbose Bash tool description with minimal one.

    For subagents that only need basic command execution.
    Also handles run_in_background parameter - only mentions TaskOutput if available.
    Strips verbose text from both tool description and input_schema.
    """
    tools = body.get("tools")
    if not isinstance(tools, list):
        return

    has_task_output = any(
        isinstance(t, dict) and t.get("name") == "TaskOutput" for t in tools
    )

    for tool in tools:
        if isinstance(tool, dict) and tool.get("name") == "Bash":
            # Replace top-level description
            desc = MINIMAL_BASH_DESCRIPTION
            if has_task_output:
                desc += BASH_BACKGROUND_SUFFIX
            tool["description"] = desc

            # Strip verbose description from input_schema.properties.description
            schema = tool.get("input_schema", {})
            props = schema.get("properties", {})
            desc_prop = props.get("description")
            if isinstance(desc_prop, dict) and "description" in desc_prop:
                desc_prop["description"] = MINIMAL_DESCRIPTION_PARAM

            break
