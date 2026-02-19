"""
CodeHandler — runs the CodingTool for 'code' tasks.

Called by TaskWorker when a 'code' task is dequeued.
Delegates to CodeTool (plan → execute → test → PR) and wraps the
outcome in a HandlerResult for Telegram reply + queue recording.
"""

from src.agents.handlers.newsletter_handler import HandlerResult
from src.config.settings import settings
from src.core.state_manager import StateManager
from src.core.task_queue import Task
from src.tools.code_tool import CodeTool
from src.utils.logger import get_logger

logger = get_logger("handler.code")


class CodeHandler:
    """Executes a code task autonomously and returns a HandlerResult."""

    def __init__(self, state_manager: StateManager) -> None:
        self.state_manager = state_manager

    async def handle(self, task: Task) -> HandlerResult:
        """
        Run a full coding cycle for the given task.

        Args:
            task: Task with task_type='code' and payload={'instruction': str}

        Returns:
            HandlerResult with Telegram reply and status.
        """
        instruction = (task.payload or {}).get("instruction", "").strip()
        if not instruction:
            return HandlerResult(
                task=task,
                status="failed",
                reply="Coding task has no instruction.",
                error="empty instruction",
            )

        if not settings.validate_production_config():
            return HandlerResult(
                task=task,
                status="failed",
                reply="CodingTool requires ANTHROPIC_API_KEY.",
                error="missing production config",
            )

        logger.info("code_handler_start", task_id=task.id, instruction=instruction[:80])

        try:
            result = await CodeTool().execute(instruction)
            return HandlerResult(
                task=task,
                status="done" if result.success else "failed",
                reply=result.format_reply(),
                data=result.to_dict(),
                error=result.error,
            )

        except Exception as exc:
            logger.error("code_handler_error", task_id=task.id, error=str(exc))
            return HandlerResult(
                task=task,
                status="failed",
                reply=f"CodingTool error: {exc}",
                error=str(exc),
            )
