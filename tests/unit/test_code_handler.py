"""
Unit tests for CodeHandler.

Mocks CodeTool entirely — verifies that CodeHandler:
- Passes instruction to CodeTool
- Returns done/failed HandlerResult based on CodeResult.success
- Handles empty instruction gracefully
- Handles missing production config gracefully
- Propagates exceptions as failed HandlerResult
"""

from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.handlers.code_handler import CodeHandler
from src.core.task_queue import Task


def _make_task(instruction: str = "fix the bug", chat_id: int = 99) -> Task:
    return Task(
        id=7,
        task_type="code",
        payload={"instruction": instruction},
        chat_id=chat_id,
    )


def _make_handler() -> CodeHandler:
    return CodeHandler(state_manager=MagicMock())


# ---------------------------------------------------------------------------
# Empty instruction
# ---------------------------------------------------------------------------


class TestEmptyInstruction:
    async def test_returns_failed_for_empty_instruction(self):
        handler = _make_handler()
        task = _make_task(instruction="")
        result = await handler.handle(task)
        assert result.status == "failed"
        assert "instruction" in result.reply.lower()

    async def test_returns_failed_for_whitespace_only(self):
        handler = _make_handler()
        task = _make_task(instruction="   ")
        result = await handler.handle(task)
        assert result.status == "failed"


# ---------------------------------------------------------------------------
# Missing production config
# ---------------------------------------------------------------------------


class TestMissingConfig:
    async def test_returns_failed_when_no_api_key(self):
        handler = _make_handler()
        task = _make_task()
        with patch("src.agents.handlers.code_handler.settings") as mock_settings:
            mock_settings.validate_production_config.return_value = False
            result = await handler.handle(task)
        assert result.status == "failed"
        assert "ANTHROPIC_API_KEY" in result.reply


# ---------------------------------------------------------------------------
# Successful coding task
# ---------------------------------------------------------------------------


class TestSuccessfulTask:
    async def test_returns_done_on_success(self):
        handler = _make_handler()
        task = _make_task()
        from src.tools.code_tool import CodeResult

        mock_result = CodeResult(
            success=True,
            instruction="fix the bug",
            branch="pa/fix-the-bug",
            tests_passed=True,
            test_output="1 passed",
            summary="Fixed the bug in main.py",
            pr_url="https://github.com/test/repo/pull/42",
        )
        with (
            patch("src.agents.handlers.code_handler.settings") as mock_settings,
            patch("src.agents.handlers.code_handler.CodeTool") as MockCodeTool,
        ):
            mock_settings.validate_production_config.return_value = True
            MockCodeTool.return_value.execute = AsyncMock(return_value=mock_result)
            result = await handler.handle(task)

        assert result.status == "done"
        assert result.task is task

    async def test_reply_contains_pr_url(self):
        handler = _make_handler()
        task = _make_task()
        from src.tools.code_tool import CodeResult

        mock_result = CodeResult(
            success=True,
            instruction="fix the bug",
            branch="pa/fix-the-bug",
            tests_passed=True,
            test_output="1 passed",
            summary="Done.",
            pr_url="https://github.com/test/repo/pull/42",
        )
        with (
            patch("src.agents.handlers.code_handler.settings") as mock_settings,
            patch("src.agents.handlers.code_handler.CodeTool") as MockCodeTool,
        ):
            mock_settings.validate_production_config.return_value = True
            MockCodeTool.return_value.execute = AsyncMock(return_value=mock_result)
            result = await handler.handle(task)

        assert "https://github.com" in result.reply

    async def test_data_contains_branch_and_pr(self):
        handler = _make_handler()
        task = _make_task()
        from src.tools.code_tool import CodeResult

        mock_result = CodeResult(
            success=True,
            instruction="fix",
            branch="pa/fix",
            tests_passed=True,
            test_output="",
            summary="",
            pr_url="https://github.com/test/repo/pull/1",
        )
        with (
            patch("src.agents.handlers.code_handler.settings") as mock_settings,
            patch("src.agents.handlers.code_handler.CodeTool") as MockCodeTool,
        ):
            mock_settings.validate_production_config.return_value = True
            MockCodeTool.return_value.execute = AsyncMock(return_value=mock_result)
            result = await handler.handle(task)

        assert result.data["branch"] == "pa/fix"
        assert result.data["pr_url"] == "https://github.com/test/repo/pull/1"


# ---------------------------------------------------------------------------
# Failed coding task (tests don't pass)
# ---------------------------------------------------------------------------


class TestFailedTask:
    async def test_returns_failed_when_tests_fail(self):
        handler = _make_handler()
        task = _make_task()
        from src.tools.code_tool import CodeResult

        mock_result = CodeResult(
            success=False,
            instruction="fix the bug",
            branch="pa/fix-the-bug",
            tests_passed=False,
            test_output="FAILED tests/unit/test_main.py",
            summary="",
            error="Pytest failed — branch not pushed.",
        )
        with (
            patch("src.agents.handlers.code_handler.settings") as mock_settings,
            patch("src.agents.handlers.code_handler.CodeTool") as MockCodeTool,
        ):
            mock_settings.validate_production_config.return_value = True
            MockCodeTool.return_value.execute = AsyncMock(return_value=mock_result)
            result = await handler.handle(task)

        assert result.status == "failed"
        assert result.error == "Pytest failed — branch not pushed."

    async def test_reply_includes_branch_name_on_failure(self):
        handler = _make_handler()
        task = _make_task()
        from src.tools.code_tool import CodeResult

        mock_result = CodeResult(
            success=False,
            instruction="do something",
            branch="pa/do-something",
            tests_passed=False,
            test_output="1 failed",
            summary="",
            error="Pytest failed — branch not pushed.",
        )
        with (
            patch("src.agents.handlers.code_handler.settings") as mock_settings,
            patch("src.agents.handlers.code_handler.CodeTool") as MockCodeTool,
        ):
            mock_settings.validate_production_config.return_value = True
            MockCodeTool.return_value.execute = AsyncMock(return_value=mock_result)
            result = await handler.handle(task)

        assert "pa/do-something" in result.reply


# ---------------------------------------------------------------------------
# Exception handling
# ---------------------------------------------------------------------------


class TestExceptionHandling:
    async def test_exception_in_code_tool_becomes_failed_result(self):
        handler = _make_handler()
        task = _make_task()
        with (
            patch("src.agents.handlers.code_handler.settings") as mock_settings,
            patch("src.agents.handlers.code_handler.CodeTool") as MockCodeTool,
        ):
            mock_settings.validate_production_config.return_value = True
            MockCodeTool.return_value.execute = AsyncMock(
                side_effect=RuntimeError("unexpected crash")
            )
            result = await handler.handle(task)

        assert result.status == "failed"
        assert "unexpected crash" in result.reply
        assert result.error == "unexpected crash"
