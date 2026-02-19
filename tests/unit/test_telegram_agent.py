"""
Unit tests for TelegramAgent.

Tests authorization logic and command routing without a real Telegram connection.
Uses MagicMock for Update/Context objects.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.telegram_agent import TelegramAgent


def _make_agent(owner_id: int = 42) -> TelegramAgent:
    sm = MagicMock()
    sm.set_fact = AsyncMock()
    sm.get_fact = AsyncMock(return_value=None)
    sm.get_all_facts = AsyncMock(return_value={})
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


# ---------------------------------------------------------------------------
# /remember and /recall (Phase D)
# ---------------------------------------------------------------------------


class TestMemoryCommands:
    async def test_remember_calls_set_fact_with_correct_args(self):
        agent = _make_agent()
        update = _make_update(user_id=42, chat_id=55)
        ctx = _make_context(args=["default_repo", "/home/elvern/ElvAgent"])
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_remember(update, ctx)

        agent.state_manager.set_fact.assert_awaited_once_with(
            "default_repo", "/home/elvern/ElvAgent"
        )

    def test_remember_joins_multi_word_value(self):
        """Value is all args after the key joined by spaces."""
        import asyncio

        agent = _make_agent()
        update = _make_update(user_id=42)
        ctx = _make_context(args=["key", "hello", "world"])
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            asyncio.get_event_loop().run_until_complete(agent._handle_remember(update, ctx))

        agent.state_manager.set_fact.assert_awaited_once_with("key", "hello world")

    async def test_remember_replies_confirmation(self):
        agent = _make_agent()
        update = _make_update(user_id=42)
        ctx = _make_context(args=["k", "v"])
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_remember(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "Remembered" in reply
        assert "k" in reply
        assert "v" in reply

    async def test_remember_no_args_sends_usage(self):
        agent = _make_agent()
        update = _make_update(user_id=42)
        ctx = _make_context(args=[])
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_remember(update, ctx)

        agent.state_manager.set_fact.assert_not_called()
        reply = update.message.reply_text.call_args[0][0]
        assert "Usage" in reply or "usage" in reply.lower()

    async def test_remember_only_key_no_value_sends_usage(self):
        agent = _make_agent()
        update = _make_update(user_id=42)
        ctx = _make_context(args=["key_only"])
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_remember(update, ctx)

        agent.state_manager.set_fact.assert_not_called()

    async def test_recall_key_returns_value(self):
        agent = _make_agent()
        agent.state_manager.get_fact = AsyncMock(return_value="/home/elvern/ElvAgent")
        update = _make_update(user_id=42)
        ctx = _make_context(args=["default_repo"])
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_recall(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "/home/elvern/ElvAgent" in reply

    async def test_recall_unknown_key_says_not_found(self):
        agent = _make_agent()
        agent.state_manager.get_fact = AsyncMock(return_value=None)
        update = _make_update(user_id=42)
        ctx = _make_context(args=["unknown_key"])
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_recall(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "No fact found" in reply

    async def test_recall_no_args_lists_all_facts(self):
        agent = _make_agent()
        agent.state_manager.get_all_facts = AsyncMock(
            return_value={"default_repo": "/path", "model": "sonnet"}
        )
        update = _make_update(user_id=42)
        ctx = _make_context(args=[])
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_recall(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "default_repo" in reply
        assert "model" in reply

    async def test_recall_no_args_empty_facts_says_none_stored(self):
        agent = _make_agent()
        agent.state_manager.get_all_facts = AsyncMock(return_value={})
        update = _make_update(user_id=42)
        ctx = _make_context(args=[])
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_recall(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "No facts" in reply


# ---------------------------------------------------------------------------
# Memory context in code task payload (Phase D)
# ---------------------------------------------------------------------------


class TestCodeTaskMemoryContext:
    async def test_first_message_has_empty_context(self):
        """No prior messages → context list is empty in task payload."""
        agent = _make_agent()
        update = _make_update(user_id=42, text="fix the bug", chat_id=55)
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_free_text(update, _make_context())

        call_args = agent.task_queue.push.call_args
        payload = call_args[0][1]
        assert payload["context"] == []

    async def test_prior_messages_appear_in_context(self):
        """Messages added before the task appear in the task payload context."""
        agent = _make_agent()
        agent.memory_store.add_message(55, "user", "what's the plan?")
        agent.memory_store.add_message(55, "assistant", "fix the tests first")

        update = _make_update(user_id=42, text="now fix them", chat_id=55)
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_free_text(update, _make_context())

        call_args = agent.task_queue.push.call_args
        payload = call_args[0][1]
        assert len(payload["context"]) == 2
        assert payload["context"][0]["role"] == "user"
        assert payload["context"][1]["role"] == "assistant"

    async def test_current_instruction_excluded_from_context(self):
        """The current instruction is passed as 'instruction', not duplicated in context."""
        agent = _make_agent()
        update = _make_update(user_id=42, text="do the thing", chat_id=55)
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_free_text(update, _make_context())

        call_args = agent.task_queue.push.call_args
        payload = call_args[0][1]
        # The current instruction was added to memory then sliced off
        assert payload["context"] == []
        assert payload["instruction"] == "do the thing"

    async def test_ack_message_has_no_phase_warning(self):
        """Phase C warning text has been removed from the acknowledgment."""
        agent = _make_agent()
        update = _make_update(user_id=42, text="do something", chat_id=55)
        with patch.object(agent, "_authorize", new=AsyncMock(return_value=True)):
            await agent._handle_free_text(update, _make_context())

        reply = update.message.reply_text.call_args[0][0]
        assert "Phase C" not in reply
        assert "CodingTool arrives" not in reply
