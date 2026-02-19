"""
Unit tests for CodeHandler.

Mocks CodeTool entirely — verifies that CodeHandler:
- Passes instruction to CodeTool
- Returns done/failed HandlerResult based on CodeResult.success
- Handles empty instruction gracefully
- Handles missing production config gracefully
- Propagates exceptions as failed HandlerResult
- Enriches instruction with conversation context and repo path (Phase D)
"""

from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.handlers.code_handler import CodeHandler, _build_full_instruction
from src.core.task_queue import Task


def _make_task(instruction: str = "fix the bug", chat_id: int = 99) -> Task:
    return Task(
        id=7,
        task_type="code",
        payload={"instruction": instruction},
        chat_id=chat_id,
    )


def _make_handler() -> CodeHandler:
    sm = MagicMock()
    sm.get_fact = AsyncMock(return_value=None)
    return CodeHandler(state_manager=sm)


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


# ---------------------------------------------------------------------------
# _build_full_instruction helper (Phase D)
# ---------------------------------------------------------------------------


class TestBuildFullInstruction:
    def test_no_context_includes_repo_and_instruction(self):
        result = _build_full_instruction("fix the bug", [], "/my/repo")
        assert "Working repository: /my/repo" in result
        assert "fix the bug" in result

    def test_context_prepended_before_repo(self):
        ctx = [{"role": "user", "content": "plan?", "ts": 1.0}]
        result = _build_full_instruction("do it", ctx, "/repo")
        assert result.index("Recent conversation context:") < result.index("Working repository:")

    def test_context_lines_formatted_correctly(self):
        ctx = [
            {"role": "user", "content": "hello", "ts": 1.0},
            {"role": "assistant", "content": "hi back", "ts": 2.0},
        ]
        result = _build_full_instruction("proceed", ctx, "/repo")
        assert "[user] hello" in result
        assert "[assistant] hi back" in result

    def test_entries_without_content_skipped(self):
        ctx = [{"role": "user", "content": "", "ts": 1.0}]
        result = _build_full_instruction("do it", ctx, "/repo")
        assert "Recent conversation context:" not in result

    def test_instruction_always_last_section(self):
        ctx = [{"role": "user", "content": "ctx", "ts": 1.0}]
        result = _build_full_instruction("my instruction", ctx, "/repo")
        assert result.endswith("my instruction")


# ---------------------------------------------------------------------------
# Context enrichment in handle() (Phase D)
# ---------------------------------------------------------------------------


def _make_success_result():
    from src.tools.code_tool import CodeResult

    return CodeResult(
        success=True,
        instruction="",
        branch="pa/fix",
        tests_passed=True,
        test_output="1 passed",
        summary="Done.",
        pr_url="https://github.com/test/repo/pull/1",
    )


class TestContextEnrichment:
    async def test_context_messages_prepended_in_instruction(self):
        handler = _make_handler()
        task = Task(
            id=7,
            task_type="code",
            payload={
                "instruction": "do it now",
                "context": [
                    {"role": "user", "content": "what's the plan?", "ts": 1.0},
                    {"role": "assistant", "content": "fix the tests", "ts": 2.0},
                ],
            },
            chat_id=99,
        )
        mock_result = _make_success_result()
        with (
            patch("src.agents.handlers.code_handler.settings") as mock_settings,
            patch("src.agents.handlers.code_handler.CodeTool") as MockCodeTool,
        ):
            mock_settings.validate_production_config.return_value = True
            MockCodeTool.return_value.execute = AsyncMock(return_value=mock_result)
            await handler.handle(task)

        instruction_used = MockCodeTool.return_value.execute.call_args[0][0]
        assert "Recent conversation context:" in instruction_used
        assert "[user] what's the plan?" in instruction_used
        assert "[assistant] fix the tests" in instruction_used
        assert "do it now" in instruction_used

    async def test_no_context_passes_instruction_without_context_block(self):
        handler = _make_handler()
        task = _make_task(instruction="fix the bug")
        mock_result = _make_success_result()
        with (
            patch("src.agents.handlers.code_handler.settings") as mock_settings,
            patch("src.agents.handlers.code_handler.CodeTool") as MockCodeTool,
        ):
            mock_settings.validate_production_config.return_value = True
            MockCodeTool.return_value.execute = AsyncMock(return_value=mock_result)
            await handler.handle(task)

        instruction_used = MockCodeTool.return_value.execute.call_args[0][0]
        assert "Recent conversation context:" not in instruction_used
        assert "fix the bug" in instruction_used


# ---------------------------------------------------------------------------
# Default repo resolution (Phase D)
# ---------------------------------------------------------------------------


class TestDefaultRepo:
    async def test_uses_default_repo_fact_when_set(self):
        sm = MagicMock()
        sm.get_fact = AsyncMock(return_value="/custom/repo")
        handler = CodeHandler(state_manager=sm)
        task = _make_task(instruction="fix the bug")
        mock_result = _make_success_result()
        with (
            patch("src.agents.handlers.code_handler.settings") as mock_settings,
            patch("src.agents.handlers.code_handler.CodeTool") as MockCodeTool,
        ):
            mock_settings.validate_production_config.return_value = True
            MockCodeTool.return_value.execute = AsyncMock(return_value=mock_result)
            await handler.handle(task)

        instruction_used = MockCodeTool.return_value.execute.call_args[0][0]
        assert "Working repository: /custom/repo" in instruction_used

    async def test_falls_back_to_settings_when_no_fact(self):
        handler = _make_handler()  # get_fact returns None
        task = _make_task(instruction="fix the bug")
        mock_result = _make_success_result()
        with (
            patch("src.agents.handlers.code_handler.settings") as mock_settings,
            patch("src.agents.handlers.code_handler.CodeTool") as MockCodeTool,
        ):
            mock_settings.validate_production_config.return_value = True
            mock_settings.pa_working_dir = "/default/elvagent"
            MockCodeTool.return_value.execute = AsyncMock(return_value=mock_result)
            await handler.handle(task)

        instruction_used = MockCodeTool.return_value.execute.call_args[0][0]
        assert "Working repository: /default/elvagent" in instruction_used
