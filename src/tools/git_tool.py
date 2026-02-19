"""
GitTool — branch / commit / push / PR operations for PA coding tasks.

Uses asyncio.create_subprocess_exec directly (bypasses ShellTool allowlist)
so that `gh` (GitHub CLI) can be called alongside `git`.

All operations target settings.github_repo_path.
"""

import asyncio
import re
import time
from dataclasses import dataclass

from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("tool.git")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str, max_len: int = 40) -> str:
    """Convert a string to a lowercase hyphenated slug."""
    return _SLUG_RE.sub("-", text.lower()).strip("-")[:max_len].rstrip("-")


@dataclass
class _ProcResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.returncode == 0


async def _run_proc(cmd: str, *args: str, cwd: str) -> _ProcResult:
    """Run a command and capture stdout/stderr."""
    proc = await asyncio.create_subprocess_exec(
        cmd,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await proc.communicate()
    return _ProcResult(
        returncode=proc.returncode if proc.returncode is not None else 0,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )


class GitTool:
    """High-level git and GitHub CLI operations for the repo."""

    def __init__(self) -> None:
        self._repo = str(settings.github_repo_path)

    # ------------------------------------------------------------------
    # Branch
    # ------------------------------------------------------------------

    @staticmethod
    def make_slug(instruction: str) -> str:
        """Turn an instruction string into a branch slug (max 40 chars)."""
        words = instruction.split()[:6]
        return _slugify(" ".join(words), max_len=40)

    def branch_name(self, slug: str) -> str:
        return f"{settings.pa_branch_prefix}/{slug}"

    async def create_branch(self, slug: str) -> str:
        """Create and checkout pa/<slug> from current HEAD. Returns branch name.

        If a branch with the same slug already exists (e.g. from a previous
        failed attempt), a 6-digit timestamp suffix is appended so the new
        branch is always unique and the old branch is preserved for inspection.
        """
        branch = self.branch_name(slug)
        result = await _run_proc("git", "checkout", "-b", branch, cwd=self._repo)

        if not result.success and "already exists" in result.stderr:
            # Previous run left this branch behind — append a timestamp so we
            # never clobber it; the stale branch can be inspected or cleaned up.
            suffix = str(int(time.time()))[-6:]
            branch = self.branch_name(f"{slug[:33]}-{suffix}")
            result = await _run_proc("git", "checkout", "-b", branch, cwd=self._repo)

        if not result.success:
            raise RuntimeError(f"git checkout -b {branch} failed:\n{result.stderr.strip()}")

        logger.info("git_branch_created", branch=branch)
        return branch

    async def current_branch(self) -> str:
        """Return the name of the current branch."""
        result = await _run_proc("git", "branch", "--show-current", cwd=self._repo)
        return result.stdout.strip()

    async def restore_branch(self, branch: str) -> None:
        """Switch back to `branch` (cleanup after a failed task)."""
        await _run_proc("git", "checkout", branch, cwd=self._repo)

    # ------------------------------------------------------------------
    # Commit
    # ------------------------------------------------------------------

    async def commit_all(self, message: str) -> _ProcResult:
        """Stage all changes and create a commit. Returns the raw result."""
        await _run_proc("git", "add", "-A", cwd=self._repo)
        result = await _run_proc("git", "commit", "-m", message, cwd=self._repo)
        logger.info("git_committed", message=message, success=result.success)
        return result

    async def has_changes(self) -> bool:
        """Return True if there are any staged or unstaged changes."""
        result = await _run_proc("git", "status", "--porcelain", cwd=self._repo)
        return bool(result.stdout.strip())

    # ------------------------------------------------------------------
    # Push + PR
    # ------------------------------------------------------------------

    async def push_branch(self, branch: str) -> _ProcResult:
        """Push branch to origin with tracking."""
        result = await _run_proc("git", "push", "-u", "origin", branch, cwd=self._repo)
        logger.info("git_pushed", branch=branch, success=result.success)
        return result

    async def create_pr(self, title: str, body: str, branch: str) -> str:
        """Create a GitHub PR and return its URL."""
        result = await _run_proc(
            "gh",
            "pr",
            "create",
            "--title",
            title,
            "--body",
            body,
            "--head",
            branch,
            cwd=self._repo,
        )
        if not result.success:
            raise RuntimeError(f"gh pr create failed:\n{result.stderr.strip()}")
        # `gh pr create` prints the PR URL as the last line
        pr_url = result.stdout.strip().splitlines()[-1]
        logger.info("pr_created", url=pr_url, branch=branch)
        return pr_url
