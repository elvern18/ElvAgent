"""
NewsletterHandler — force-triggers a full newsletter cycle.

Called by TaskWorker when a 'newsletter' task is dequeued.
Runs the Orchestrator pipeline (research → enhance → publish → record)
regardless of when the last newsletter ran.
"""

from dataclasses import dataclass, field

from src.config.settings import settings
from src.core.content_pipeline import ContentPipeline
from src.core.orchestrator import CycleResult, Orchestrator
from src.core.state_manager import StateManager
from src.core.task_queue import Task
from src.publishing.discord_publisher import DiscordPublisher
from src.publishing.markdown_publisher import MarkdownPublisher
from src.publishing.telegram_publisher import TelegramPublisher
from src.publishing.twitter_publisher import TwitterPublisher
from src.research.arxiv_researcher import ArXivResearcher
from src.research.huggingface_researcher import HuggingFaceResearcher
from src.research.techcrunch_researcher import TechCrunchResearcher
from src.research.venturebeat_researcher import VentureBeatResearcher
from src.utils.logger import get_logger

logger = get_logger("handler.newsletter")


@dataclass
class HandlerResult:
    """Outcome of any task handler execution."""

    task: Task
    status: str  # "done" or "failed"
    reply: str  # Telegram reply message to send
    data: dict | None = field(default=None)  # result payload for TaskQueue.update()
    error: str | None = field(default=None)  # error string on failure


class NewsletterHandler:
    """Runs the full newsletter Orchestrator cycle on demand."""

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager

    async def handle(self, task: Task) -> HandlerResult:
        """
        Execute a newsletter cycle and return a formatted result.

        Args:
            task: The dequeued 'newsletter' task (payload may be empty)

        Returns:
            HandlerResult with Telegram reply and status
        """
        logger.info("newsletter_handler_start", task_id=task.id)

        if not settings.validate_production_config():
            return HandlerResult(
                task=task,
                status="failed",
                reply="Newsletter failed: missing production config (ANTHROPIC_API_KEY?).",
                error="production config invalid",
            )

        try:
            result = await self._run_cycle()
            reply = self._format_reply(result)
            return HandlerResult(
                task=task,
                status="done",
                reply=reply,
                data={
                    "platforms": result.platforms_published,
                    "item_count": result.item_count,
                    "cost": result.total_cost,
                },
            )
        except Exception as exc:
            logger.error("newsletter_handler_failed", task_id=task.id, error=str(exc))
            return HandlerResult(
                task=task,
                status="failed",
                reply=f"Newsletter failed: {exc}",
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_orchestrator(self) -> Orchestrator:
        researchers = [
            ArXivResearcher(max_items=5),
            HuggingFaceResearcher(max_items=5),
            VentureBeatResearcher(max_items=5),
            TechCrunchResearcher(max_items=5),
        ]
        publishers = [
            TelegramPublisher(),
            TwitterPublisher(),
            DiscordPublisher(),
            MarkdownPublisher(),
        ]
        return Orchestrator(
            state_manager=self.state_manager,
            researchers=researchers,
            publishers=publishers,
            pipeline=ContentPipeline(self.state_manager),
        )

    async def _run_cycle(self) -> CycleResult:
        return await self._build_orchestrator().run_cycle(mode="production")

    @staticmethod
    def _format_reply(result: CycleResult) -> str:
        if not result.success:
            return f"Newsletter failed: {result.error}"
        platforms = ", ".join(result.platforms_published) if result.platforms_published else "none"
        return (
            f"Newsletter published!\n"
            f"Platforms : {platforms}\n"
            f"Items     : {result.item_count}\n"
            f"Cost      : ${result.total_cost:.4f}"
        )
