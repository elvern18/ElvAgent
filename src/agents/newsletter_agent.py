"""
NewsletterAgent — AgentLoop wrapper around the newsletter Orchestrator.

Polls every 60 s. Triggers a full newsletter cycle if no newsletter has
been published in the last NEWSLETTER_INTERVAL_MINUTES minutes.

Integrates cleanly into MasterAgent via run_forever() — no scheduler
library required; the AgentLoop base class handles the timing loop.
"""

from dataclasses import dataclass

from src.agents.base import AgentLoop
from src.config.settings import settings
from src.core.content_pipeline import ContentPipeline
from src.core.orchestrator import CycleResult, Orchestrator
from src.core.state_manager import StateManager
from src.publishing.discord_publisher import DiscordPublisher
from src.publishing.markdown_publisher import MarkdownPublisher
from src.publishing.telegram_publisher import TelegramPublisher
from src.publishing.twitter_publisher import TwitterPublisher
from src.research.arxiv_researcher import ArXivResearcher
from src.research.huggingface_researcher import HuggingFaceResearcher
from src.research.techcrunch_researcher import TechCrunchResearcher
from src.research.venturebeat_researcher import VentureBeatResearcher
from src.utils.logger import get_logger

logger = get_logger("newsletter_agent")

# Trigger newsletter if last run was older than this
NEWSLETTER_INTERVAL_MINUTES = 55


@dataclass
class NewsletterEvent:
    """Trigger event: run a newsletter cycle."""

    triggered_by: str  # 'schedule' or 'manual'
    minutes_since_last: float


class NewsletterAgent(AgentLoop):
    """
    Periodic newsletter agent using the ReAct loop.

    poll()   → query DB for minutes since last newsletter
    triage() → emit NewsletterEvent if overdue
    act()    → run full Orchestrator cycle (research → publish)
    record() → already handled inside Orchestrator.run_cycle()
    """

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager

    def _build_orchestrator(self) -> Orchestrator:
        """Build a fresh Orchestrator with all production publishers."""
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
        pipeline = ContentPipeline(self.state_manager)
        return Orchestrator(
            state_manager=self.state_manager,
            researchers=researchers,
            publishers=publishers,
            pipeline=pipeline,
        )

    async def poll(self) -> list[float]:
        """
        Check how long ago the last newsletter was published.

        Returns:
            [minutes_since_last] — single-element list
        """
        minutes = await self.state_manager.minutes_since_last_newsletter()
        return [minutes]

    async def triage(self, snapshots: list[float]) -> list[NewsletterEvent]:
        """
        Decide whether a newsletter run is due.

        Returns:
            [NewsletterEvent] if overdue, [] otherwise
        """
        if not snapshots:
            return []

        minutes = snapshots[0]
        if minutes >= NEWSLETTER_INTERVAL_MINUTES:
            logger.info(
                "newsletter_overdue",
                minutes_since_last=f"{minutes:.1f}",
                threshold=NEWSLETTER_INTERVAL_MINUTES,
            )
            return [NewsletterEvent(triggered_by="schedule", minutes_since_last=minutes)]

        logger.debug(
            "newsletter_not_due",
            minutes_since_last=f"{minutes:.1f}",
            minutes_until_next=f"{NEWSLETTER_INTERVAL_MINUTES - minutes:.1f}",
        )
        return []

    async def act(self, events: list[NewsletterEvent]) -> list[CycleResult]:
        """Run the newsletter Orchestrator for each trigger event."""
        results = []
        for event in events:
            logger.info(
                "newsletter_cycle_starting",
                triggered_by=event.triggered_by,
                minutes_since_last=f"{event.minutes_since_last:.1f}",
            )
            if not settings.validate_production_config():
                logger.error("newsletter_skipped", reason="production config invalid")
                continue
            orchestrator = self._build_orchestrator()
            result = await orchestrator.run_cycle(mode="production")
            results.append(result)
        return results

    async def record(self, results: list[CycleResult]) -> None:
        """Orchestrator.run_cycle() handles its own recording — just log here."""
        for result in results:
            if result.success:
                logger.info(
                    "newsletter_cycle_done",
                    platforms=result.platforms_published,
                    cost=f"${result.total_cost:.4f}",
                )
            else:
                logger.error("newsletter_cycle_failed", error=result.error)
