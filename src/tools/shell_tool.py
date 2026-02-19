"""
ShellTool — restricted async subprocess execution.

Only commands in settings.pa_allowed_commands are permitted.
Uses asyncio.create_subprocess_exec (never shell=True) to prevent injection.
"""

import asyncio
from dataclasses import dataclass

from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("tool.shell")

DEFAULT_TIMEOUT = 120  # seconds

# Cap individual stream lengths so long-running commands don't flood LLM context.
_MAX_OUTPUT_CHARS = 20_000


@dataclass
class ShellResult:
    """Result of a shell command execution."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.returncode == 0

    def __str__(self) -> str:
        parts = []
        if self.stdout:
            parts.append(self.stdout.rstrip())
        if self.stderr:
            parts.append(f"[stderr]\n{self.stderr.rstrip()}")
        if not parts:
            parts.append(f"(exit {self.returncode})")
        return "\n".join(parts)

    def truncated_str(self) -> str:
        """Like __str__ but caps each stream at _MAX_OUTPUT_CHARS.

        Use this when passing output to an LLM to prevent context explosion.
        """

        def _cap(text: str) -> str:
            if len(text) <= _MAX_OUTPUT_CHARS:
                return text
            return (
                text[:_MAX_OUTPUT_CHARS] + f"\n...[truncated — {len(text):,} chars total,"
                f" showing first {_MAX_OUTPUT_CHARS:,}]"
            )

        parts = []
        if self.stdout:
            parts.append(_cap(self.stdout.rstrip()))
        if self.stderr:
            parts.append(f"[stderr]\n{_cap(self.stderr.rstrip())}")
        if not parts:
            parts.append(f"(exit {self.returncode})")
        return "\n".join(parts)


class ShellTool:
    """Run allowed shell commands as async subprocesses."""

    async def run(
        self,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> ShellResult:
        """
        Execute `command [args...]` in a subprocess.

        Raises:
            PermissionError: if command is not in pa_allowed_commands.
            asyncio.TimeoutError: caught internally; returns ShellResult with
                returncode=-1 and a timeout message in stderr.
        """
        if command not in settings.pa_allowed_commands:
            raise PermissionError(
                f"Command {command!r} is not in the allowed list. "
                f"Allowed: {settings.pa_allowed_commands}"
            )
        argv = [command, *(args or [])]
        cwd_str = cwd or str(settings.pa_working_dir)
        logger.info("shell_run", command=command, args=args, cwd=cwd_str)

        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd_str,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return ShellResult(
                returncode=proc.returncode if proc.returncode is not None else 0,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return ShellResult(
                returncode=-1,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
            )
