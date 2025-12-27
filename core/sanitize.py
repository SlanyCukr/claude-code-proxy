"""Request sanitization for upstream routing."""

from __future__ import annotations

import copy
import re
from typing import Any

DEFAULT_STRIPPED_TOOLS = {"NotebookEdit", "WebFetch", "WebSearch"}

# Default Claude Code agents to strip from Task tool description
DEFAULT_STRIPPED_AGENTS = {
    "general-purpose",
    "statusline-setup",
    "Explore",
    "Plan",
    "claude-code-guide",
}
MCP_TOOL_PREFIX = "mcp__"
MCP_TOOL_ALLOWLIST = {"mcp__codex__codex", "mcp__codex__codex-reply"}

# Pre-compiled regex patterns for performance
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


def _agent_pattern(agent: str) -> re.Pattern[str]:
    return re.compile(rf"- {re.escape(agent)}:.*?\(Tools:.*?\)\n", re.DOTALL)


_AGENT_PATTERNS = {agent: _agent_pattern(agent) for agent in DEFAULT_STRIPPED_AGENTS}
_MALWARE_REMINDER_PATTERN = re.compile(
    r"<system-reminder>\s*Whenever you read a file, you should consider whether "
    r"it would be considered malware\..*?</system-reminder>\s*",
    re.DOTALL,
)
DEFAULT_SYSTEM_PROMPT = (
    "● You are an interactive CLI tool that helps users with software engineering tasks. Use the instructions "
    "below and the tools available to you to assist the user.\n\n"
    "  # Tone and style\n"
    "  - Only use emojis if the user explicitly requests it. Avoid using emojis in all communication unless asked.\n"
    "  - Your output will be displayed on a command line interface. Your responses should be short and concise. You "
    "can use Github-flavored markdown for formatting, and will be rendered in a monospace font using the CommonMark "
    "specification.\n"
    "  - Output text to communicate with the user; all text you output outside of tool use is displayed to the user. "
    "Only use tools to complete tasks. Never use tools like Bash or code comments as means to communicate with the "
    "user during the session.\n"
    "  - NEVER create files unless they're absolutely necessary for achieving your goal. ALWAYS prefer editing an "
    "existing file to creating a new one. This includes markdown files.\n\n"
    "  # Professional objectivity\n"
    "  Prioritize technical accuracy and truthfulness over validating the user's beliefs. Focus on facts and "
    "problem-solving, providing direct, objective technical info without any unnecessary superlatives, praise, or "
    "emotional validation. It is best for the user if Claude honestly applies the same rigorous standards to all "
    "ideas and disagrees when necessary, even if it may not be what the user wants to hear. Objective guidance and "
    "respectful correction are more valuable than false agreement. Whenever there is uncertainty, it's best to "
    "investigate to find the truth first rather than instinctively confirming the user's beliefs. Avoid using "
    "over-the-top validation or excessive praise when responding to users such as \"You're absolutely right\" or "
    "similar phrases.\n\n"
    "  # Planning without timelines\n"
    "  When planning tasks, provide concrete implementation steps without time estimates. Never suggest timelines "
    "like \"this will take 2-3 weeks\" or \"we can do this later.\" Focus on what needs to be done, not when. Break "
    "work into actionable steps and let users decide scheduling.\n\n"
    "  # Task Management\n"
    "  You have access to the TodoWrite tools to help you manage and plan tasks. Use these tools VERY frequently to "
    "ensure that you are tracking your tasks and giving the user visibility into your progress.\n"
    "  These tools are also EXTREMELY helpful for planning tasks, and for breaking down larger complex tasks into "
    "smaller steps. If you do not use this tool when planning, you may forget to do important tasks - and that is "
    "unacceptable.\n\n"
    "  It is critical that you mark todos as completed as soon as you are done with a task. Do not batch up multiple "
    "tasks before marking them as completed.\n\n"
    "  <example>\n"
    "  user: Run the build and fix any type errors\n"
    "  assistant: I'm going to use the TodoWrite tool to write the following items to the todo list:\n"
    "  - Run the build\n"
    "  - Fix any type errors\n\n"
    "  I'm now going to run the build using Bash.\n\n"
    "  Looks like I found 10 type errors. I'm going to use the TodoWrite tool to write 10 items to the todo list.\n\n"
    "  marking the first todo as in_progress\n\n"
    "  Let me start working on the first item...\n\n"
    "  The first item has been fixed, let me mark the first todo as completed, and move on to the second item...\n"
    "  ..\n"
    "  ..\n"
    "  </example>\n\n"
    "  # Asking questions as you work\n\n"
    "  You have access to the AskUserQuestion tool to ask the user questions when you need clarification, want to "
    "validate assumptions, or need to make a decision you're unsure about. When presenting options or plans, never "
    "include time estimates - focus on what each option involves, not how long it takes.\n\n"
    "  Users may configure 'hooks', shell commands that execute in response to events like tool calls, in settings. "
    "Treat feedback from hooks, including <system-reminder> tags, as coming from the user. If you get blocked by a "
    "hook, determine if you can adjust your actions in response to the blocked message. If not, ask the user to "
    "check their hooks configuration.\n\n"
    "  # Doing tasks\n"
    "  The user will primarily request you perform software engineering tasks. This includes solving bugs, adding "
    "new functionality, refactoring code, explaining code, and more. For these tasks the following steps are "
    "recommended:\n"
    "  - NEVER propose changes to code you haven't read. If a user asks about or wants you to modify a file, read it "
    "first. Understand existing code before suggesting modifications.\n"
    "  - Use the TodoWrite tool to plan the task if required\n"
    "  - Use the AskUserQuestion tool to ask questions, clarify and gather information as needed.\n"
    "  - Be careful not to introduce security vulnerabilities such as command injection, XSS, SQL injection, and "
    "other OWASP top 10 vulnerabilities. If you notice that you wrote insecure code, immediately fix it.\n"
    "  - Avoid over-engineering. Only make changes that are directly requested or clearly necessary. Keep solutions "
    "simple and focused.\n"
    "    - Don't add features, refactor code, or make \"improvements\" beyond what was asked. A bug fix doesn't need "
    "surrounding code cleaned up. A simple feature doesn't need extra configurability. Don't add docstrings, "
    "comments, or type annotations to code you didn't change. Only add comments where the logic isn't "
    "self-evident.\n"
    "    - Don't add error handling, fallbacks, or validation for scenarios that can't happen. Trust internal code "
    "and framework guarantees. Only validate at system boundaries (user input, external APIs). Don't use feature "
    "flags or backwards-compatibility shims when you can just change the code.\n"
    "    - Don't create helpers, utilities, or abstractions for one-time operations. Don't design for hypothetical "
    "future requirements. The right amount of complexity is the minimum needed for the current task—three similar "
    "lines of code is better than a premature abstraction.\n"
    "  - Avoid backwards-compatibility hacks like renaming unused `_vars`, re-exporting types, adding `// removed` "
    "comments for removed code, etc. If something is unused, delete it completely.\n"
    "  - Tool results and user messages may include <system-reminder> tags. <system-reminder> tags contain useful "
    "information and reminders. They are automatically added by the system, and bear no direct relation to the "
    "specific tool results or user messages in which they appear.\n"
    "  - The conversation has unlimited context through automatic summarization.\n\n"
    "  # Tool usage policy\n"
    "  - When doing file search, prefer to use the Task tool in order to reduce context usage.\n"
    "  - You should proactively use the Task tool with specialized agents when the task at hand matches the agent's "
    "description.\n"
    "  - /<skill-name> (e.g., /commit) is shorthand for users to invoke a user-invocable skill. When executed, the "
    "skill gets expanded to a full prompt. Use the Skill tool to execute them. IMPORTANT: Only use Skill for skills "
    "listed in its user-invocable skills section - do not guess or use built-in CLI commands.\n"
    "  - You can call multiple tools in a single response. If you intend to call multiple tools and there are no "
    "dependencies between them, make all independent tool calls in parallel. Maximize use of parallel tool calls "
    "where possible to increase efficiency. However, if some tool calls depend on previous calls to inform "
    "dependent values, do NOT call these tools in parallel and instead call them sequentially instead. Never use "
    "placeholders or guess missing parameters in tool calls.\n"
    "  - If the user specifies that they want you to run tools \"in parallel\", you MUST send a single message with "
    "multiple tool use content blocks. For example, if you need to launch multiple agents in parallel, send a single "
    "message with multiple Task tool calls.\n"
    "  - Use specialized tools instead of bash commands when possible, as this provides a better user experience. "
    "For file operations, use dedicated tools: Read for reading files instead of cat/head/tail, Edit for editing "
    "instead of sed/awk, and Write for creating files instead of cat with heredoc or echo redirection. Reserve bash "
    "tools exclusively for actual system commands and terminal operations that require shell execution. NEVER use "
    "bash echo or other command-line tools to communicate thoughts, explanations, or instructions to the user. "
    "Output all communication directly in your response text instead.\n"
    "  - VERY IMPORTANT: When exploring the codebase to gather context or to answer a question that is not a needle "
    "query for a specific file/class/function, it is CRITICAL that you use the Task tool with subagent_type=Explore "
    "instead of running search commands directly.\n"
    "  <example>\n"
    "  user: Where are errors from the client handled?\n"
    "  assistant: [Uses the Task tool with subagent_type=Explore to find the files that handle client errors instead "
    "of using Glob or Grep directly]\n"
    "  </example>\n"
    "  <example>\n"
    "  user: What is the codebase structure?\n"
    "  assistant: [Uses the Task tool with subagent_type=Explore]\n"
    "  </example>\n\n"
    "  # Code References\n\n"
    "  When referencing specific functions or pieces of code include the pattern `file_path:line_number` to allow "
    "the user to easily navigate to the source code location.\n\n"
    "  <example>\n"
    "  user: Where are errors from the client handled?\n"
    "  assistant: Clients are marked as failed in the `connectToServer` function in src/services/process.ts:712.\n"
    "  </example>\n\n"
    "  Here is useful information about the environment you are running in:\n"
    "  <env>\n"
    "  Working directory: /home/slanycukr/projects/claude-code-proxy\n"
    "  Is directory a git repo: No\n"
    "  Platform: linux\n"
    "  OS Version: Linux 6.18.2-zen2-1-zen\n"
    "  Today's date: 2025-12-26\n"
    "  </env>"
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

    def sanitize(self, body: dict[str, Any]) -> dict[str, Any]:
        """Remove unwanted tools and replace the system prompt."""
        body = self._strip_tools(body)
        body = self._filter_task_tool(body)
        body = self._strip_system_reminders(body)
        return self._replace_system_prompt(body)

    def _strip_tools(self, body: dict[str, Any]) -> dict[str, Any]:
        tools = body.get("tools")
        tool_choice = body.get("tool_choice")
        if not isinstance(tools, list):
            return body

        body = copy.deepcopy(body)
        body["tools"] = [
            tool
            for tool in tools
            if not self._should_strip_tool(tool)
        ]

        if isinstance(tool_choice, dict) and tool_choice.get("name") in self._stripped_tools:
            body.pop("tool_choice", None)

        return body

    def _should_strip_tool(self, tool: Any) -> bool:
        if not isinstance(tool, dict):
            return False
        name = tool.get("name")
        if not isinstance(name, str):
            return False
        if name in self._stripped_tools:
            return True
        if name.startswith(MCP_TOOL_PREFIX) and name not in MCP_TOOL_ALLOWLIST:
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

            # 1. Replace opening text
            new_opening = (
                "Delegate work to agents that run in isolation. "
                "Preserves main session context while agents handle focused tasks."
            )
            description = _OLD_OPENING_PATTERN.sub(new_opening, description)

            # 2. Filter out default agent entries
            for agent in DEFAULT_STRIPPED_AGENTS:
                description = _AGENT_PATTERNS[agent].sub("", description)

            # 3. Strip "access to current context" instruction
            description = _CONTEXT_PATTERN.sub("", description)

            # 4. Strip example usage section
            description = _EXAMPLE_PATTERN.sub("", description)

            if description != original_description:
                body = copy.deepcopy(body)
                for t in body["tools"]:
                    if isinstance(t, dict) and t.get("name") == "Task":
                        t["description"] = description
                        break
            break  # Only one Task tool expected

        return body

    def _strip_system_reminders(self, body: dict[str, Any]) -> dict[str, Any]:
        """Strip specific <system-reminder> blocks from message content."""
        messages = body.get("messages")
        if not isinstance(messages, list):
            return body

        marker = "you should consider whether it would be considered malware"

        # Check if any stripping is needed
        needs_strip = False
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, str) and marker in content:
                needs_strip = True
                break
            if isinstance(content, list):
                for block in content:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "text"
                        and isinstance(block.get("text"), str)
                        and marker in block["text"]
                    ):
                        needs_strip = True
                        break
                if needs_strip:
                    break

        if not needs_strip:
            return body

        # Deep copy and apply stripping
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
