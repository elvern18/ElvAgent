"""
TaskWorker — AgentLoop that processes tasks from the TaskQueue.

poll()   → claim the next pending task (5 s interval)
triage() → pass-through (task already claimed atomically by pop())
act()    → dispatch to the correct handler
record() → mark task done/failed in DB + send Telegram reply to chat_id
"""

from src.agents.base import AgentLoop
from src.agents.handlers.code_handler import CodeHandler
from src.agents.handlers.newsletter_handler import HandlerResult, NewsletterHandler
from src.agents.handlers.status_handler import StatusHandler
from src.config.settings import settings
from src.core.state_manager import StateManager
from src.core.task_queue import Task, TaskQueue
from src.utils.logger import get_logger

logger = get_logger("task_worker")


class TaskWorker(AgentLoop):
    """
    Drains the TaskQueue and dispatches each task to its handler.

    Runs every 5 seconds (configured in MasterAgent). A crash inside
    a single task is caught and recorded — the worker keeps running.
    """

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.task_queue = TaskQueue()

    # ------------------------------------------------------------------
    # AgentLoop interface
    # ------------------------------------------------------------------

    async def poll(self) -> list[Task]:
        """Claim the next pending task; return empty list if queue is empty."""
        task = await self.task_queue.pop()
        return [task] if task else []

    async def triage(self, tasks: list[Task]) -> list[Task]:
        """Pass-through — tasks are already claimed when popped."""
        return tasks

    async def act(self, tasks: list[Task]) -> list[HandlerResult]:
        """Dispatch each task to its handler. Exceptions are caught per-task."""
        results = []
        for task in tasks:
            result = await self._dispatch(task)
            results.append(result)
        return results

    async def record(self, results: list[HandlerResult]) -> None:
        """Persist outcome to DB and send Telegram reply if chat_id is set."""
        for result in results:
            await self.task_queue.update(
                task_id=result.task.id,
                status=result.status,
                result=result.data,
                error=result.error,
            )
            if result.task.chat_id and result.reply:
                await self._send_reply(result.task.chat_id, result.reply)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, task: Task) -> HandlerResult:
        """Route task to the correct handler. Never raises — errors become HandlerResult."""
        logger.info("task_dispatching", task_id=task.id, task_type=task.task_type)
        try:
            if task.task_type == "newsletter":
                return await NewsletterHandler(self.state_manager).handle(task)

            if task.task_type == "status":
                # Edge case: status task was queued rather than handled inline
                status_text = await StatusHandler(self.state_manager).get_status()
                return HandlerResult(task=task, status="done", reply=status_text)

            if task.task_type == "code":
                return await CodeHandler(self.state_manager).handle(task)

            if task.task_type == "shell":
                return HandlerResult(
                    task=task,
                    status="done",
                    reply="Shell task dispatched to code handler.",
                )

            return HandlerResult(
                task=task,
                status="failed",
                reply=f"Unknown task type: {task.task_type!r}",
                error=f"No handler registered for task type {task.task_type!r}",
            )

        except Exception as exc:
            logger.error(
                "task_dispatch_error",
                task_id=task.id,
                task_type=task.task_type,
                error=str(exc),
            )
            return HandlerResult(
                task=task,
                status="failed",
                reply=f"Task #{task.id} failed: {exc}",
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Telegram reply
    # ------------------------------------------------------------------

    async def _send_reply(self, chat_id: int, text: str) -> None:
        """Send a plain-text message to a Telegram chat."""
        if not settings.telegram_bot_token:
            logger.warning("telegram_reply_skipped", reason="TELEGRAM_BOT_TOKEN not set")
            return
        try:
            from telegram import Bot

            async with Bot(token=settings.telegram_bot_token) as bot:
                await bot.send_message(chat_id=chat_id, text=text)
        except Exception as exc:
            logger.error("telegram_reply_failed", chat_id=chat_id, error=str(exc))
