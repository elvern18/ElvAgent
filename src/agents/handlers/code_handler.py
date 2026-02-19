"""
CodeHandler — runs the CodingTool for 'code' tasks.

Called by TaskWorker when a 'code' task is dequeued.

Execution flow
--------------
1. If the task payload contains no ``clarify_answer``, ask CodeTool.clarify()
   whether clarifying questions are needed.  If so, return a
   status="waiting_clarification" HandlerResult so TaskWorker can pause the
   task and send the questions to the user via Telegram.

2. Once an answer is present (or no questions were needed), build the full
   instruction and delegate to CodeTool (plan → execute → test → PR).

Instruction enrichment
-----------------------
The instruction forwarded to CodeTool is enriched with:
- Prior conversation context from the task payload
- Working repository path (from default_repo fact or settings fallback)
- Clarification answer from the user (if any)
"""

from src.agents.handlers.newsletter_handler import HandlerResult
from src.config.settings import settings
from src.core.state_manager import StateManager
from src.core.task_queue import Task
from src.tools.code_tool import CodeTool
from src.utils.logger import get_logger

logger = get_logger("handler.code")


def _build_full_instruction(
    instruction: str,
    context: list[dict],
    repo: str,
    clarify_answer: str | None = None,
) -> str:
    """
    Assemble the full instruction string for CodeTool.

    Sections (in order, each separated by a blank line):
    1. Recent conversation context (if any)
    2. Working repository path
    3. Clarification answer from the user (if any)
    4. The raw instruction
    """
    parts = []
    if context:
        lines = [f"[{m['role']}] {m['content']}" for m in context if m.get("content")]
        if lines:
            parts.append("Recent conversation context:\n" + "\n".join(lines))
    parts.append(f"Working repository: {repo}")
    if clarify_answer:
        parts.append(f"Clarification from user:\n{clarify_answer}")
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
            task: Task with task_type='code' and payload containing at minimum
                  {'instruction': str}.  Optional keys: 'context', 'clarify_answer'.

        Returns:
            HandlerResult with one of three statuses:
            - 'waiting_clarification': questions sent to user, task is paused
            - 'done': coding succeeded, PR opened
            - 'failed': coding or tests failed
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
        clarify_answer = payload.get("clarify_answer")
        repo = await self.state_manager.get_fact("default_repo") or str(settings.pa_working_dir)

        code_tool = CodeTool()

        # ----------------------------------------------------------------
        # Step 1: clarification phase (skipped if we already have an answer)
        # ----------------------------------------------------------------
        if not clarify_answer:
            questions = await code_tool.clarify(instruction)
            if questions:
                logger.info(
                    "code_handler_needs_clarification",
                    task_id=task.id,
                    instruction=instruction[:80],
                )
                return HandlerResult(
                    task=task,
                    status="waiting_clarification",
                    reply=(
                        "Before I start coding, I need to clarify a few things:\n\n"
                        f"{questions}\n\n"
                        "Please reply with your answers and I'll get started."
                    ),
                    data={"clarify_questions": questions},
                )

        # ----------------------------------------------------------------
        # Step 2: execute
        # ----------------------------------------------------------------
        full_instruction = _build_full_instruction(instruction, context, repo, clarify_answer)
        logger.info("code_handler_start", task_id=task.id, instruction=instruction[:80])

        try:
            result = await code_tool.execute(full_instruction)
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
