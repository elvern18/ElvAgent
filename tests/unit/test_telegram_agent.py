"""
Unit tests for TelegramAgent.

Tests authorization logic and command routing without a real Telegram connection.
Uses MagicMock for Update/Context objects.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.telegram_agent import TelegramAgent


def _make_agent(owner_id: int = 42) -> TelegramAgent:
    sm = MagicMock()
    agent = TelegramAgent(state_manager=sm)
    agent.task_queue = MagicMock()
    agent.task_queue.push = AsyncMock(return_value=1)
    return agent


def _make_update(user_id: int, text: str = "", chat_id: int = 100) -> MagicMock:
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.username = "testuser"
    update.effective_chat.id = chat_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


def _make_context(args: list[str] | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.args = args or []
    return ctx


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


class TestAuthorize:
    async def test_authorized_user_passes(self):
        agent = _make_agent(owner_id=42)
        update = _make_update(user_id=42)
        with patch("src.agents.telegram_agent.settings") as mock_settings:
            mock_settings.telegram_owner_id = 42
            result = await agent._authorize(update)
        assert result is True
        update.message.reply_text.assert_not_called()

    async def test_unauthorized_user_rejected(self):
        agent = _make_agent(owner_id=42)
        update = _make_update(user_id=999)
        with patch("src.agents.telegram_agent.settings") as mock_settings:
            mock_settings.telegram_owner_id = 42
            result = await agent._authorize(update)
        assert result is False
        update.message.reply_text.assert_awaited_once_with("Unauthorized.")


# ---------------------------------------------------------------------------
# /start and /help
# ---------------------------------------------------------------------------


class TestInlineCommands:
    async def test_start_replies_online_message(self):
        agent = _make_agent()
        update = _make_update(user_id=42)
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_start(update, _make_context())
        update.message.reply_text.assert_awaited_once()
        args = update.message.reply_text.call_args[0][0]
        assert "online" in args.lower()

    async def test_help_replies_with_command_list(self):
        agent = _make_agent()
        update = _make_update(user_id=42)
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_help(update, _make_context())
        args = update.message.reply_text.call_args[0][0]
        assert "/status" in args
        assert "/newsletter" in args
        assert "/code" in args

    async def test_unauthorized_start_does_not_reply_further(self):
        agent = _make_agent()
        update = _make_update(user_id=999)
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=False)):
            await agent._handle_start(update, _make_context())
        # reply_text called by _authorize only (mocked to False so body skipped)
        update.message.reply_text.assert_not_called()


# ---------------------------------------------------------------------------
# /status (inline)
# ---------------------------------------------------------------------------


class TestStatusCommand:
    async def test_status_calls_status_handler_inline(self):
        agent = _make_agent()
        update = _make_update(user_id=42)
        # StatusHandler is imported lazily inside _handle_status — patch at source
        with (
            patch.object(agent, "_authorize", new=AsyncMock(return_value=True)),
            patch(
                "src.agents.handlers.status_handler.StatusHandler.get_status",
                new=AsyncMock(return_value="ok status"),
            ),
        ):
            await agent._handle_status(update, _make_context())

        update.message.reply_text.assert_awaited_once_with("ok status")

    async def test_status_does_not_push_to_queue(self):
        agent = _make_agent()
        update = _make_update(user_id=42)
        with (
            patch.object(agent, "_authorize", new=AsyncMock(return_value=True)),
            patch(
                "src.agents.handlers.status_handler.StatusHandler.get_status",
                new=AsyncMock(return_value="ok"),
            ),
        ):
            await agent._handle_status(update, _make_context())

        agent.task_queue.push.assert_not_called()


# ---------------------------------------------------------------------------
# /newsletter
# ---------------------------------------------------------------------------


class TestNewsletterCommand:
    async def test_newsletter_pushes_to_queue_priority_1(self):
        agent = _make_agent()
        update = _make_update(user_id=42, chat_id=77)
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_newsletter(update, _make_context())

        agent.task_queue.push.assert_awaited_once_with("newsletter", {}, chat_id=77, priority=1)

    async def test_newsletter_sends_acknowledgment(self):
        agent = _make_agent()
        update = _make_update(user_id=42, chat_id=77)
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_newsletter(update, _make_context())

        args = update.message.reply_text.call_args[0][0]
        assert "task #1" in args.lower() or "#1" in args


# ---------------------------------------------------------------------------
# /code
# ---------------------------------------------------------------------------


class TestCodeCommand:
    async def test_code_with_args_queues_task(self):
        agent = _make_agent()
        update = _make_update(user_id=42, chat_id=55)
        ctx = _make_context(args=["fix", "the", "bug"])
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_code(update, ctx)

        agent.task_queue.push.assert_awaited_once()
        call_args = agent.task_queue.push.call_args
        assert call_args[0][0] == "code"
        assert "fix the bug" in call_args[0][1]["instruction"]

    async def test_code_without_args_replies_usage(self):
        agent = _make_agent()
        update = _make_update(user_id=42)
        ctx = _make_context(args=[])
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_code(update, ctx)

        agent.task_queue.push.assert_not_called()
        args = update.message.reply_text.call_args[0][0]
        assert "Usage" in args or "usage" in args.lower()

    async def test_code_acknowledgment_contains_task_id(self):
        agent = _make_agent()
        update = _make_update(user_id=42, chat_id=55)
        ctx = _make_context(args=["do", "something"])
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_code(update, ctx)

        args = update.message.reply_text.call_args[0][0]
        assert "#1" in args


# ---------------------------------------------------------------------------
# Free-form text
# ---------------------------------------------------------------------------


class TestFreeText:
    async def test_free_text_treated_as_code(self):
        agent = _make_agent()
        update = _make_update(user_id=42, text="add a readme", chat_id=55)
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_free_text(update, _make_context())

        agent.task_queue.push.assert_awaited_once()
        call_args = agent.task_queue.push.call_args
        assert call_args[0][0] == "code"
        assert "add a readme" in call_args[0][1]["instruction"]

    async def test_free_text_unauthorized_does_nothing(self):
        agent = _make_agent()
        update = _make_update(user_id=999, text="add a readme")
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=False)):
            await agent._handle_free_text(update, _make_context())

        agent.task_queue.push.assert_not_called()
