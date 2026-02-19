"""
TelegramAgent — bidirectional Telegram interface.

Receives messages from the authorised owner, validates identity, and either:
  - handles inline   (/start, /help, /status → instant reply, no queue)
  - queues for async (/newsletter, /code, free-form text → TaskQueue)

Uses python-telegram-bot v20+ async Application API.
TaskWorker processes queued tasks and sends the result reply.
"""

import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.config.settings import settings
from src.core.state_manager import StateManager
from src.core.task_queue import TaskQueue
from src.utils.logger import get_logger

logger = get_logger("telegram_agent")

_HELP_TEXT = """
ElvAgent commands:

/start      — greeting
/status     — current agent status
/newsletter — trigger newsletter now
/code <instruction> — code task (Phase C)
/help       — this message

Free-form text is treated as /code.
""".strip()


class TelegramAgent:
    """
    Bidirectional Telegram interface built on python-telegram-bot v20+ Application.

    Security: every handler calls _authorize() first. Messages from any user
    other than TELEGRAM_OWNER_ID are rejected with an "Unauthorized." reply.
    """

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.task_queue = TaskQueue()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def run_forever(self) -> None:
        """Start polling and block until the coroutine is cancelled."""
        app = self._build_application()
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)

        logger.info(
            "telegram_agent_polling",
            owner_id=settings.telegram_owner_id,
        )

        try:
            # Yield control to the event loop; PTB handles messages in the background.
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("telegram_agent_shutting_down")
            await app.updater.stop()
            await app.stop()
            await app.shutdown()

    # ------------------------------------------------------------------
    # Application builder
    # ------------------------------------------------------------------

    def _build_application(self) -> Application:
        app = Application.builder().token(settings.telegram_bot_token).build()
        app.add_handler(CommandHandler("start", self._handle_start))
        app.add_handler(CommandHandler("help", self._handle_help))
        app.add_handler(CommandHandler("status", self._handle_status))
        app.add_handler(CommandHandler("newsletter", self._handle_newsletter))
        app.add_handler(CommandHandler("code", self._handle_code))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_free_text))
        return app

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------

    async def _authorize(self, update: Update) -> bool:
        """
        Return True if the sender is the configured owner.
        Reply "Unauthorized." and return False otherwise.
        """
        if update.effective_user.id != settings.telegram_owner_id:
            await update.message.reply_text("Unauthorized.")
            logger.warning(
                "telegram_unauthorized",
                user_id=update.effective_user.id,
                username=update.effective_user.username,
            )
            return False
        return True

    # ------------------------------------------------------------------
    # Inline command handlers
    # ------------------------------------------------------------------

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorize(update):
            return
        await update.message.reply_text("ElvAgent online.\nType /help for available commands.")

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorize(update):
            return
        await update.message.reply_text(_HELP_TEXT)

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Return status inline (instant, no queue)."""
        if not await self._authorize(update):
            return
        from src.agents.handlers.status_handler import StatusHandler

        status_text = await StatusHandler(self.state_manager).get_status()
        await update.message.reply_text(status_text)

    # ------------------------------------------------------------------
    # Queued command handlers
    # ------------------------------------------------------------------

    async def _handle_newsletter(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Queue a newsletter task and acknowledge immediately."""
        if not await self._authorize(update):
            return
        chat_id = update.effective_chat.id
        task_id = await self.task_queue.push("newsletter", {}, chat_id=chat_id, priority=1)
        await update.message.reply_text(
            f"Starting newsletter... (task #{task_id})\nI'll reply here when it's done."
        )

    async def _handle_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Queue a coding task from /code <instruction>."""
        if not await self._authorize(update):
            return
        instruction = " ".join(context.args) if context.args else ""
        if not instruction:
            await update.message.reply_text(
                "Usage: /code <instruction>\nExample: /code fix the type error in main.py"
            )
            return
        await self._queue_code_task(update, instruction)

    async def _handle_free_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Treat free-form text as a /code shorthand."""
        if not await self._authorize(update):
            return
        instruction = update.message.text.strip()
        await self._queue_code_task(update, instruction)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    async def _queue_code_task(self, update: Update, instruction: str) -> None:
        """Push a code task to the queue and send an acknowledgment."""
        chat_id = update.effective_chat.id
        task_id = await self.task_queue.push(
            "code",
            {"instruction": instruction, "repo": str(settings.pa_working_dir)},
            chat_id=chat_id,
            priority=5,
        )
        preview = instruction[:80] + ("..." if len(instruction) > 80 else "")
        await update.message.reply_text(
            f"Coding task queued (#{task_id}).\n"
            f"Instruction: {preview}\n\n"
            "\u26a0\ufe0f CodingTool arrives in Phase C."
        )
