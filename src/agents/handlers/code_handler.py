"""
CodeHandler — runs the CodingTool for 'code' tasks.

Called by TaskWorker when a 'code' task is dequeued.
Delegates to CodeTool (plan → execute → test → PR) and wraps the
outcome in a HandlerResult for Telegram reply + queue recording.

Enriches the instruction with:
- Prior conversation context from the task payload
- Working repository path (from default_repo fact or settings fallback)
"""

from src.agents.handlers.newsletter_handler import HandlerResult
from src.config.settings import settings
from src.core.state_manager import StateManager
from src.core.task_queue import Task
from src.tools.code_tool import CodeTool
from src.utils.logger import get_logger

logger = get_logger("handler.code")


def _build_full_instruction(instruction: str, context: list[dict], repo: str) -> str:
    """
    Assemble the full instruction string for CodeTool, prepending any
    conversation context and the resolved working repository path.
    """
    parts = []
    if context:
        lines = [f"[{m['role']}] {m['content']}" for m in context if m.get("content")]
        if lines:
            parts.append("Recent conversation context:\n" + "\n".join(lines))
    parts.append(f"Working repository: {repo}")
    parts.append(instruction)
    return "\n\n".join(parts)


class CodeHandler:
    """Executes a code task autonomously and returns a HandlerResult."""

    def __init__(self, state_manager: StateManager) -> None:
        self.state_manager = state_manager

    async def handle(self, task: Task) -> HandlerResult:
        """
        Run a full coding cycle for the given task.

        Args:
            task: Task with task_type='code' and payload={'instruction': str,
                  'context': list[dict] (optional)}

        Returns:
            HandlerResult with Telegram reply and status.
        """
        payload = task.payload or {}
        instruction = payload.get("instruction", "").strip()
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

        context = payload.get("context", [])
        repo = await self.state_manager.get_fact("default_repo") or str(settings.pa_working_dir)
        full_instruction = _build_full_instruction(instruction, context, repo)

        logger.info("code_handler_start", task_id=task.id, instruction=instruction[:80])

        try:
            result = await CodeTool().execute(full_instruction)
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
