"""
Unit tests for ShellTool.

Uses real asyncio subprocesses for integration-style checks (python -c),
and mocks asyncio.create_subprocess_exec for the timeout/error edge cases.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.shell_tool import ShellResult, ShellTool

# ---------------------------------------------------------------------------
# ShellResult
# ---------------------------------------------------------------------------


class TestShellResult:
    def test_success_true_when_returncode_zero(self):
        r = ShellResult(returncode=0, stdout="ok", stderr="")
        assert r.success is True

    def test_success_false_when_nonzero(self):
        r = ShellResult(returncode=1, stdout="", stderr="err")
        assert r.success is False

    def test_str_includes_stdout(self):
        r = ShellResult(returncode=0, stdout="hello", stderr="")
        assert "hello" in str(r)

    def test_str_includes_stderr_label(self):
        r = ShellResult(returncode=1, stdout="", stderr="oops")
        assert "[stderr]" in str(r)

    def test_str_shows_exit_code_when_no_output(self):
        r = ShellResult(returncode=42, stdout="", stderr="")
        assert "42" in str(r)


# ---------------------------------------------------------------------------
# Command allowlist
# ---------------------------------------------------------------------------


class TestAllowlist:
    async def test_disallowed_command_raises_permission_error(self):
        tool = ShellTool()
        with patch("src.tools.shell_tool.settings") as m:
            m.pa_allowed_commands = ["pytest"]
            with pytest.raises(PermissionError, match="not in the allowed list"):
                await tool.run("rm", ["-rf", "/"], cwd="/tmp")

    async def test_allowed_command_does_not_raise_allowlist_error(self):
        tool = ShellTool()
        with (
            patch("src.tools.shell_tool.settings") as m,
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        ):
            m.pa_allowed_commands = ["python"]
            m.pa_working_dir = "/tmp"
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"hi\n", b""))
            proc.returncode = 0
            mock_exec.return_value = proc
            result = await tool.run("python", ["-c", "print('hi')"])
        assert result.success


# ---------------------------------------------------------------------------
# Successful execution
# ---------------------------------------------------------------------------


class TestSuccessfulRun:
    async def test_captures_stdout(self):
        tool = ShellTool()
        with (
            patch("src.tools.shell_tool.settings") as m,
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        ):
            m.pa_allowed_commands = ["python"]
            m.pa_working_dir = "/tmp"
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"hello world\n", b""))
            proc.returncode = 0
            mock_exec.return_value = proc
            result = await tool.run("python", ["-c", "print('hello world')"])
        assert "hello world" in result.stdout
        assert result.success

    async def test_captures_stderr(self):
        tool = ShellTool()
        with (
            patch("src.tools.shell_tool.settings") as m,
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        ):
            m.pa_allowed_commands = ["python"]
            m.pa_working_dir = "/tmp"
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"", b"warning\n"))
            proc.returncode = 0
            mock_exec.return_value = proc
            result = await tool.run("python", [])
        assert "warning" in result.stderr

    async def test_nonzero_exit_code_preserved(self):
        tool = ShellTool()
        with (
            patch("src.tools.shell_tool.settings") as m,
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        ):
            m.pa_allowed_commands = ["python"]
            m.pa_working_dir = "/tmp"
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"", b"fail"))
            proc.returncode = 1
            mock_exec.return_value = proc
            result = await tool.run("python", ["-c", "exit(1)"])
        assert result.returncode == 1
        assert not result.success

    async def test_cwd_forwarded_to_subprocess(self):
        tool = ShellTool()
        captured = {}
        with (
            patch("src.tools.shell_tool.settings") as m,
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        ):
            m.pa_allowed_commands = ["python"]
            m.pa_working_dir = "/tmp"

            async def capture_cwd(*args, **kwargs):
                captured["cwd"] = kwargs.get("cwd")
                proc = MagicMock()
                proc.communicate = AsyncMock(return_value=(b"", b""))
                proc.returncode = 0
                return proc

            mock_exec.side_effect = capture_cwd
            await tool.run("python", [], cwd="/custom/path")

        assert captured["cwd"] == "/custom/path"


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# truncated_str
# ---------------------------------------------------------------------------


class TestTruncatedStr:
    def test_short_output_unchanged(self):
        r = ShellResult(returncode=0, stdout="hello", stderr="")
        assert r.truncated_str() == str(r)

    def test_long_stdout_truncated(self):
        from src.tools.shell_tool import _MAX_OUTPUT_CHARS

        big = "x" * (_MAX_OUTPUT_CHARS + 100)
        r = ShellResult(returncode=0, stdout=big, stderr="")
        result = r.truncated_str()
        assert len(result) < len(big)
        assert "truncated" in result

    def test_long_stderr_truncated(self):
        from src.tools.shell_tool import _MAX_OUTPUT_CHARS

        big = "e" * (_MAX_OUTPUT_CHARS + 100)
        r = ShellResult(returncode=1, stdout="", stderr=big)
        result = r.truncated_str()
        assert "truncated" in result
        assert "[stderr]" in result

    def test_str_not_affected_by_truncated_str(self):
        """__str__ is unchanged — it does not truncate."""
        from src.tools.shell_tool import _MAX_OUTPUT_CHARS

        big = "y" * (_MAX_OUTPUT_CHARS + 100)
        r = ShellResult(returncode=0, stdout=big, stderr="")
        assert len(str(r)) > _MAX_OUTPUT_CHARS  # full output in __str__

    def test_empty_output_shows_exit_code(self):
        r = ShellResult(returncode=7, stdout="", stderr="")
        assert "7" in r.truncated_str()


class TestTimeout:
    async def test_timeout_returns_failed_result(self):
        tool = ShellTool()
        with (
            patch("src.tools.shell_tool.settings") as m,
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
            patch("asyncio.wait_for", side_effect=asyncio.TimeoutError),
        ):
            m.pa_allowed_commands = ["python"]
            m.pa_working_dir = "/tmp"
            proc = MagicMock()
            proc.kill = MagicMock()
            mock_exec.return_value = proc
            result = await tool.run("python", [], timeout=1)

        assert result.returncode == -1
        assert "timed out" in result.stderr.lower()
        assert not result.success
