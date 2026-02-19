"""
TelegramAgent — bidirectional Telegram interface.

Receives messages from the authorised owner, validates identity, and either:
  - handles inline   (/start, /help, /status → instant reply, no queue)
  - queues for async (/newsletter, /code → TaskQueue)
  - routes free text (/new_chat, clarification replies, smart classify)

Free-text routing
-----------------
1. If a waiting_clarification task exists for this chat → resume that task.
2. Otherwise, use a lightweight Haiku classifier to decide:
   - "code"         → queue as a coding task (existing flow)
   - "conversation" → reply immediately with Sonnet using full chat history

Context
-------
MemoryStore is persistent (no TTL) — conversation history accumulates until
the user explicitly sends /new_chat to clear it.

Uses python-telegram-bot v20+ async Application API.
"""

import asyncio

import anthropic
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.config.settings import settings
from src.core.state_manager import StateManager
from src.core.task_queue import Task, TaskQueue
from src.memory.memory_store import MemoryStore
from src.utils.logger import get_logger

logger = get_logger("telegram_agent")

_HELP_TEXT = """
ElvAgent commands:

/start      — greeting
/status     — current agent status
/newsletter — trigger newsletter now
/code <instruction> — autonomous coding task
/new_chat   — clear conversation history and start fresh
/remember <key> <value> — persist a fact (e.g. /remember default_repo /path/to/repo)
/recall [key] — retrieve a fact, or list all facts
/help       — this message

Free-form text is classified automatically:
  • Coding/programming task → queued as /code
  • Conversation or question → answered directly
""".strip()


def _to_api_messages(messages: list) -> list[dict]:
    """Convert MemoryStore Message objects to Claude API message format.

    Ensures the list starts with a 'user' role and that consecutive
    messages with the same role are merged (Claude requires alternating).
    """
    if not messages:
        return []

    # Build raw list
    raw = [{"role": m.role, "content": m.content} for m in messages]

    # Merge consecutive same-role messages
    merged: list[dict] = [raw[0]]
    for msg in raw[1:]:
        if msg["role"] == merged[-1]["role"]:
            merged[-1] = {
                "role": msg["role"],
                "content": merged[-1]["content"] + "\n" + msg["content"],
            }
        else:
            merged.append(msg)

    # Drop leading assistant messages (Claude requires starting with 'user')
    while merged and merged[0]["role"] != "user":
        merged.pop(0)

    return merged


class TelegramAgent:
    """
    Bidirectional Telegram interface built on python-telegram-bot v20+ Application.

    Security: every handler calls _authorize() first. Messages from any user
    other than TELEGRAM_OWNER_ID are rejected with an "Unauthorized." reply.
    """

    _CLASSIFY_MODEL = "claude-haiku-4-5-20251001"
    _CONVERSE_MODEL = "claude-sonnet-4-6"

    def __init__(self, state_manager: StateManager, memory_store: MemoryStore | None = None):
        self.state_manager = state_manager
        self.memory_store = memory_store or MemoryStore()
        self.task_queue = TaskQueue()
        # Lazy Anthropic client — only initialised when an API call is needed
        self._anthropic: anthropic.AsyncAnthropic | None = None

    # ------------------------------------------------------------------
    # Anthropic client (lazy)
    # ------------------------------------------------------------------

    def _get_client(self) -> anthropic.AsyncAnthropic:
        """Return (creating if necessary) the shared Anthropic client."""
        if self._anthropic is None:
            self._anthropic = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._anthropic

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
        app.add_handler(CommandHandler("new_chat", self._handle_new_chat))
        app.add_handler(CommandHandler("remember", self._handle_remember))
        app.add_handler(CommandHandler("recall", self._handle_recall))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_free_text))
        return app

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------

    async def _authorize(self, update: Update) -> bool:
        """Return True if the sender is the configured owner, False otherwise."""
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

    async def _handle_new_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Clear conversation history for this chat and start fresh."""
        if not await self._authorize(update):
            return
        chat_id = update.effective_chat.id
        self.memory_store.clear(chat_id)
        await update.message.reply_text(
            "Conversation cleared. Starting fresh — what would you like to do?"
        )
        logger.info("memory_cleared", chat_id=chat_id)

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

    async def _handle_remember(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Persist a key/value fact: /remember <key> <value>."""
        if not await self._authorize(update):
            return
        args = context.args or []
        if len(args) < 2:
            await update.message.reply_text(
                "Usage: /remember <key> <value>\n"
                "Example: /remember default_repo /home/elvern/ElvAgent"
            )
            return
        key = args[0]
        value = " ".join(args[1:])
        await self.state_manager.set_fact(key, value)
        await update.message.reply_text(f"Remembered: {key} = {value}")

    async def _handle_recall(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Retrieve a fact: /recall <key>, or list all facts with /recall."""
        if not await self._authorize(update):
            return
        args = context.args or []
        if args:
            key = args[0]
            value = await self.state_manager.get_fact(key)
            if value is None:
                await update.message.reply_text(f"No fact found for '{key}'.")
            else:
                await update.message.reply_text(value)
        else:
            facts = await self.state_manager.get_all_facts()
            if not facts:
                await update.message.reply_text("No facts stored.")
            else:
                lines = [f"• {k} = {v}" for k, v in facts.items()]
                await update.message.reply_text("\n".join(lines))

    # ------------------------------------------------------------------
    # Free-text handler — smart routing
    # ------------------------------------------------------------------

    async def _handle_free_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Route free-form text based on context.

        Priority order:
        1. If a coding task is waiting for clarification → resume it.
        2. Classify the message: code task or conversational reply.
        """
        if not await self._authorize(update):
            return

        text = update.message.text.strip()
        chat_id = update.effective_chat.id

        # 1. Resume any paused coding task first
        waiting_task = await self.task_queue.find_waiting_clarification(chat_id)
        if waiting_task:
            await self._resume_clarification(update, waiting_task, text)
            return

        # 2. Classify: code task vs. conversational message
        route = await self._classify_message(text)
        if route == "code":
            await self._queue_code_task(update, text)
        else:
            await self._handle_conversation(update, text)

    # ------------------------------------------------------------------
    # Clarification resume
    # ------------------------------------------------------------------

    async def _resume_clarification(self, update: Update, task: Task, answer: str) -> None:
        """Store the user's clarification answer and re-queue the paused task."""
        chat_id = update.effective_chat.id
        self.memory_store.add_message(chat_id, "user", answer)
        await self.task_queue.resume_with_answer(task.id, answer)
        await update.message.reply_text(f"Got it! Starting coding now... (task #{task.id})")
        logger.info("clarification_received", task_id=task.id, chat_id=chat_id)

    # ------------------------------------------------------------------
    # Smart message classifier
    # ------------------------------------------------------------------

    async def _classify_message(self, text: str) -> str:
        """Use Haiku to classify text as 'code' or 'conversation'.

        Falls back to 'code' if the API is unavailable (fail-safe —
        worst case the user gets a code-task acknowledgment for a
        conversational message, which is recoverable).
        """
        try:
            client = self._get_client()
            response = await client.messages.create(
                model=self._CLASSIFY_MODEL,
                max_tokens=5,
                system=(
                    "Classify the user message as exactly one of two categories:\n"
                    "  code        — a coding, programming, or software-building task\n"
                    "  conversation — a question, chat, acknowledgment, or follow-up\n"
                    "Reply with exactly one word: code or conversation."
                ),
                messages=[{"role": "user", "content": text}],
            )
            label = (response.content[0].text or "").strip().lower() if response.content else ""
            return "code" if "code" in label else "conversation"
        except Exception as exc:
            logger.warning("classify_message_failed", error=str(exc))
            return "code"  # safe fallback

    # ------------------------------------------------------------------
    # Conversational reply
    # ------------------------------------------------------------------

    async def _handle_conversation(self, update: Update, text: str) -> None:
        """Reply directly using Sonnet with full conversation history as context."""
        chat_id = update.effective_chat.id
        self.memory_store.add_message(chat_id, "user", text)

        api_messages = _to_api_messages(self.memory_store.get_context(chat_id))
        if not api_messages:
            api_messages = [{"role": "user", "content": text}]

        try:
            client = self._get_client()
            response = await client.messages.create(
                model=self._CONVERSE_MODEL,
                max_tokens=1024,
                system=(
                    "You are ElvAgent, an autonomous AI assistant. "
                    "Answer conversationally and helpfully. "
                    "For coding tasks the user should use /code."
                ),
                messages=api_messages,
            )
            reply = (
                response.content[0].text if response.content else "Sorry, I couldn't process that."
            )
        except Exception as exc:
            logger.error("conversation_reply_failed", error=str(exc))
            reply = f"Error generating reply: {exc}"

        self.memory_store.add_message(chat_id, "assistant", reply)
        await update.message.reply_text(reply)

    # ------------------------------------------------------------------
    # Code-task helper
    # ------------------------------------------------------------------

    async def _queue_code_task(self, update: Update, instruction: str) -> None:
        """Push a code task to the queue and send an acknowledgment."""
        chat_id = update.effective_chat.id
        self.memory_store.add_message(chat_id, "user", instruction)
        prior_context = [m.to_dict() for m in self.memory_store.get_context(chat_id)[:-1]]
        task_id = await self.task_queue.push(
            "code",
            {
                "instruction": instruction,
                "repo": str(settings.pa_working_dir),
                "context": prior_context,
            },
            chat_id=chat_id,
            priority=5,
        )
        preview = instruction[:80] + ("..." if len(instruction) > 80 else "")
        await update.message.reply_text(f"Coding task queued (#{task_id}).\nInstruction: {preview}")
