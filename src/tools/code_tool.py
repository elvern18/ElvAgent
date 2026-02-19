"""
CodeTool — autonomous three-phase coding execution.

Phase 0 (clarify): Haiku checks whether the instruction needs clarification.
                   Returns questions for the user, or None to proceed.
Phase 1 (plan):    Haiku generates a concise implementation plan.
Phase 2 (execute): Sonnet with tool_use implements the plan using
                   filesystem and shell tools.

After execution:
- Run pytest as a final gate.
- If tests pass → push branch + create PR.
- If tests fail → keep branch locally, report failure.

Context management:
- Tool results are capped at _MAX_TOOL_RESULT_CHARS to prevent token explosion.
- Noisy directories (.venv, .git, etc.) are excluded from all tool calls.
- The message list passed to Sonnet is trimmed to a sliding window so that
  accumulated history never exceeds the model's context limit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import anthropic

from src.config.settings import settings
from src.tools.filesystem_tool import FilesystemTool
from src.tools.git_tool import GitTool
from src.tools.shell_tool import ShellTool
from src.utils.logger import get_logger

logger = get_logger("tool.code")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Directories that should never be read or listed — they're noisy and large.
_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {".venv", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", "node_modules"}
)

# Single tool-result cap: keeps each read_file / run_shell output small enough
# that even 30 accumulated results stay well under 200K tokens.
_MAX_TOOL_RESULT_CHARS = 20_000

# Sliding-window size for the Sonnet execution loop.  We always keep the
# initial user instruction plus the last N assistant/tool-result pairs.
_CONTEXT_KEEP_LAST_PAIRS = 10


# ---------------------------------------------------------------------------
# Claude tool definitions (exposed to Sonnet during the execution phase)
# ---------------------------------------------------------------------------

_CLAUDE_TOOLS: list[dict] = [
    {
        "name": "read_file",
        "description": "Read the contents of a file from the filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path or path relative to the repository root.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write text content to a file, creating parent directories as needed. "
            "Overwrites the file if it already exists."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Target file path."},
                "content": {"type": "string", "description": "UTF-8 text to write."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_dir",
        "description": "List files and subdirectories in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Directory path to list."}},
            "required": ["path"],
        },
    },
    {
        "name": "run_shell",
        "description": (
            "Run an allowed shell command in the repository directory. "
            f"Allowed commands: {settings.pa_allowed_commands}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command name (first token only, e.g. 'pytest').",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command arguments.",
                    "default": [],
                },
            },
            "required": ["command"],
        },
    },
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class CodeResult:
    """Outcome of a CodeTool.execute() call."""

    success: bool
    instruction: str
    branch: str
    tests_passed: bool
    test_output: str
    summary: str
    pr_url: str | None = field(default=None)
    error: str | None = field(default=None)

    def format_reply(self) -> str:
        if not self.success:
            lines = [
                "Coding task failed.",
                f"Branch: {self.branch} (kept locally)",
                f"Tests: {'pass' if self.tests_passed else 'FAIL'}",
            ]
            if self.error:
                lines.append(f"Error: {self.error}")
            if self.test_output:
                lines.append(f"\nTest output:\n{self.test_output[:800]}")
            return "\n".join(lines)

        lines = [
            "Coding task complete!",
            f"PR: {self.pr_url}",
            f"Branch: {self.branch}",
            "Tests: pass",
        ]
        if self.summary:
            lines.append(f"\n{self.summary}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "branch": self.branch,
            "pr_url": self.pr_url,
            "tests_passed": self.tests_passed,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate_tool_result(result: str) -> str:
    """Cap a tool result string so it never blows up LLM context.

    The truncation notice tells the model exactly what happened so it can
    adjust — e.g. request a narrower line range instead of the whole file.
    """
    if len(result) <= _MAX_TOOL_RESULT_CHARS:
        return result
    return (
        result[:_MAX_TOOL_RESULT_CHARS] + f"\n...[truncated — {len(result):,} chars total,"
        f" showing first {_MAX_TOOL_RESULT_CHARS:,}]"
    )


def _trim_messages(messages: list[dict]) -> list[dict]:
    """Sliding-window trim for the Sonnet tool-use message list.

    After the initial user instruction, messages come in (assistant, user)
    pairs.  We keep the first message plus the last N complete pairs so that
    accumulated history never causes a token-limit error.
    """
    max_total = 1 + _CONTEXT_KEEP_LAST_PAIRS * 2
    if len(messages) <= max_total:
        return messages
    return [messages[0]] + messages[-(max_total - 1) :]


def _is_excluded_path(path: str) -> str | None:
    """Return the excluded directory name if *path* passes through one, else None."""
    for part in Path(path).parts:
        if part in _EXCLUDED_DIRS:
            return part
    return None


# ---------------------------------------------------------------------------
# CodeTool
# ---------------------------------------------------------------------------


class CodeTool:
    """
    Autonomous coding tool: clarify → plan → execute → test → PR.

    Usage::

        # Check if the instruction needs clarification first:
        questions = await CodeTool().clarify(instruction)
        if questions:
            # send questions to the user; resume later with the answer

        # Then execute (optionally with user's clarification answer):
        result = await CodeTool().execute(instruction)
    """

    _PLAN_MODEL = "claude-haiku-4-5-20251001"
    _EXEC_MODEL = "claude-sonnet-4-6"

    def __init__(self) -> None:
        self._fs = FilesystemTool()
        self._shell = ShellTool()
        self._git = GitTool()
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # ------------------------------------------------------------------
    # Phase 0: Clarification check (Haiku)
    # ------------------------------------------------------------------

    async def clarify(self, instruction: str) -> str | None:
        """Ask Haiku whether the instruction needs clarification before coding.

        Returns a formatted string of numbered questions, or None if the
        instruction is clear enough to implement directly.
        """
        response = await self._client.messages.create(
            model=self._PLAN_MODEL,
            max_tokens=300,
            system=(
                "You are reviewing a coding task instruction.\n"
                "If it is clear and specific enough to implement confidently,"
                " reply with exactly: PROCEED\n"
                "If you genuinely need clarification to avoid building the wrong thing,"
                " respond with 1-5 numbered questions. Be concise."
                " Only ask truly necessary questions —"
                " not nice-to-haves or implementation details you can decide yourself."
            ),
            messages=[{"role": "user", "content": instruction}],
        )
        text = (response.content[0].text or "").strip() if response.content else ""
        if not text or text.upper().startswith("PROCEED"):
            return None
        return text

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def execute(self, instruction: str, task_label: str | None = None) -> CodeResult:
        """Plan, implement, test, and (if tests pass) push a PR for ``instruction``.

        Args:
            instruction: Full enriched instruction forwarded to the planning and
                execution phases.  May include conversation context, repo path,
                and clarification answers prepended by CodeHandler.
            task_label:  Short label used *only* for the git branch slug.  Pass
                the original user instruction here so the branch name reflects
                the user's intent rather than the enriched context prefix.
                Falls back to ``instruction`` when not provided.
        """
        slug = GitTool.make_slug(task_label or instruction)
        original_branch = await self._git.current_branch()
        branch = ""

        try:
            branch = await self._git.create_branch(slug)

            # Phase 1: planning (Haiku, cheap)
            plan = await self._plan(instruction)
            logger.info("code_plan_ready", slug=slug, plan_chars=len(plan))

            # Phase 2: execution (Sonnet with tools)
            summary, _tool_log = await self._execute(instruction, plan)
            logger.info("code_execute_done", slug=slug, summary_chars=len(summary))

            # Pytest gate
            test_result = await self._run_tests()
            test_output = str(test_result)

            if not test_result.success:
                logger.warning("code_tests_failed", slug=slug)
                return CodeResult(
                    success=False,
                    instruction=instruction,
                    branch=branch,
                    tests_passed=False,
                    test_output=test_output,
                    summary=summary,
                    error="Pytest failed — branch not pushed.",
                )

            # Commit + push + PR
            await self._git.commit_all(f"feat: {slug}")
            await self._git.push_branch(branch)
            pr_url = await self._git.create_pr(
                title=f"feat: {instruction[:72]}",
                body=(
                    f"## Summary\n\n"
                    f"Instruction: {instruction}\n\n"
                    f"## Plan\n\n{plan}\n\n"
                    f"## Notes\n\n{summary}\n\n"
                    "🤖 Opened autonomously by ElvAgent CodingTool"
                ),
                branch=branch,
            )

            return CodeResult(
                success=True,
                instruction=instruction,
                branch=branch,
                tests_passed=True,
                test_output=test_output,
                summary=summary,
                pr_url=pr_url,
            )

        except Exception as exc:
            logger.error("code_tool_error", slug=slug, error=str(exc))
            return CodeResult(
                success=False,
                instruction=instruction,
                branch=branch or slug,
                tests_passed=False,
                test_output="",
                summary="",
                error=str(exc),
            )
        finally:
            # Always return to original branch so agent loop is unaffected
            try:
                await self._git.restore_branch(original_branch)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Phase 1: Planning (Haiku)
    # ------------------------------------------------------------------

    async def _plan(self, instruction: str) -> str:
        """Call Haiku to generate a concise 3-5 step implementation plan."""
        try:
            all_entries = self._fs.list_dir(str(settings.github_repo_path))
            repo_listing = "\n".join(e for e in all_entries if e.rstrip("/") not in _EXCLUDED_DIRS)
        except Exception:
            repo_listing = "(could not list repo)"

        response = await self._client.messages.create(
            model=self._PLAN_MODEL,
            max_tokens=512,
            system=(
                "You are an expert Python developer. "
                "Given a coding instruction and the repository top-level structure, "
                "produce a concise 3-5 bullet-point implementation plan. "
                "Name specific files to modify. Do NOT write code — just the plan."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Instruction: {instruction}\n\nRepository structure:\n{repo_listing}"
                    ),
                }
            ],
        )
        return response.content[0].text if response.content else "(no plan)"

    # ------------------------------------------------------------------
    # Phase 2: Execution (Sonnet with tool_use)
    # ------------------------------------------------------------------

    async def _execute(self, instruction: str, plan: str) -> tuple[str, list[dict]]:
        """Run Sonnet in a tool_use loop. Returns (final_text, tool_call_log).

        Two key safeguards prevent the 9.7M-token explosion:
        1. Tool results are capped via _truncate_tool_result().
        2. The messages sent to the API are trimmed to a sliding window via
           _trim_messages() — the full list grows, but only a recent window
           is forwarded on each call.
        """
        system = (
            "You are an expert Python developer working on the ElvAgent codebase.\n"
            f"Repository: {settings.github_repo_path}\n"
            f"Allowed working root: {settings.pa_working_dir}\n\n"
            "Follow the plan below. Use the provided tools to read existing code, "
            "write new/modified files, and run shell commands as needed. "
            "When you are done, summarise the changes you made.\n\n"
            f"Implementation plan:\n{plan}"
        )
        messages: list[dict] = [{"role": "user", "content": instruction}]
        tool_log: list[dict] = []

        for iteration in range(settings.pa_max_tool_iterations):
            response = await self._client.messages.create(
                model=self._EXEC_MODEL,
                max_tokens=8192,
                system=system,
                tools=_CLAUDE_TOOLS,
                messages=_trim_messages(messages),
            )

            # Append the full assistant turn to the growing history
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                final_text = " ".join(
                    block.text for block in response.content if hasattr(block, "text")
                )
                return final_text or "Done.", tool_log

            if response.stop_reason != "tool_use":
                break

            # Execute each tool call and collect results
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result_text = await self._call_tool(block.name, block.input)
                tool_log.append(
                    {
                        "iter": iteration,
                        "tool": block.name,
                        "input": block.input,
                        "result_preview": result_text[:200],
                    }
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        return "Max tool iterations reached.", tool_log

    # ------------------------------------------------------------------
    # Tool dispatcher
    # ------------------------------------------------------------------

    async def _call_tool(self, name: str, tool_input: dict) -> str:
        """Execute a single Claude tool call and return the result as a string.

        Excluded directories (.venv, .git, …) are blocked.
        All results are capped at _MAX_TOOL_RESULT_CHARS.
        """
        try:
            if name == "read_file":
                path = tool_input["path"]
                excluded = _is_excluded_path(path)
                if excluded:
                    return (
                        f"Error: reading files from {excluded!r} is not allowed"
                        " (excluded directory — use a more specific path)."
                    )
                return _truncate_tool_result(self._fs.read_file(path))

            if name == "write_file":
                return self._fs.write_file(tool_input["path"], tool_input["content"])

            if name == "list_dir":
                entries = self._fs.list_dir(tool_input["path"])
                # Strip out noisy dirs so the model doesn't try to recurse into them
                visible = [e for e in entries if e.rstrip("/") not in _EXCLUDED_DIRS]
                return "\n".join(visible) if visible else "(empty directory)"

            if name == "run_shell":
                result = await self._shell.run(
                    tool_input["command"],
                    tool_input.get("args", []),
                    cwd=str(settings.github_repo_path),
                )
                return _truncate_tool_result(result.truncated_str())

            return f"Unknown tool: {name!r}"

        except Exception as exc:
            logger.warning("code_tool_call_error", tool=name, error=str(exc))
            return f"Error: {exc}"

    # ------------------------------------------------------------------
    # Pytest gate
    # ------------------------------------------------------------------

    async def _run_tests(self):
        """Run the project test suite. Returns ShellResult."""
        return await self._shell.run(
            "pytest",
            ["tests/", "-q", "--tb=short"],
            cwd=str(settings.github_repo_path),
            timeout=300,
        )
