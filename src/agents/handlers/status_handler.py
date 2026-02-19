"""
StatusHandler — builds the comprehensive /status reply.

Called inline from TelegramAgent (not via TaskQueue) for instant response.
Queries: newsletter timing, queue depth, today's API spend, agent config.
"""

import subprocess

from src.agents.newsletter_agent import NEWSLETTER_INTERVAL_MINUTES
from src.config.settings import settings
from src.core.state_manager import StateManager
from src.core.task_queue import TaskQueue
from src.utils.logger import get_logger

logger = get_logger("handler.status")


class StatusHandler:
    """Builds the /status reply from live DB data."""

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.task_queue = TaskQueue()

    async def get_status(self) -> str:
        """
        Query all relevant state and return a formatted status string.

        Returns:
            Multi-line plain text status message.
        """
        newsletter_line = await self._newsletter_line()
        queue_line = await self._queue_line()
        spend_line = await self._spend_line()
        agents_block = self._agents_block()
        branch = self._current_branch()

        return (
            f"ElvAgent Status\n\n"
            f"{newsletter_line}\n"
            f"{queue_line}\n"
            f"{spend_line}\n\n"
            f"Agents:\n"
            f"{agents_block}\n\n"
            f"Branch: {branch}"
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _newsletter_line(self) -> str:
        minutes_since = await self.state_manager.minutes_since_last_newsletter()
        if minutes_since >= 999_000:
            return "Newsletter  : never published"
        minutes_until = NEWSLETTER_INTERVAL_MINUTES - minutes_since
        if minutes_until <= 0:
            return f"Newsletter  : overdue ({minutes_since:.0f} min since last)"
        return f"Newsletter  : last {minutes_since:.0f} min ago | next in ~{minutes_until:.0f} min"

    async def _queue_line(self) -> str:
        pending = await self.task_queue.depth("pending")
        in_progress = await self.task_queue.depth("in_progress")
        return f"Queue       : {pending} pending, {in_progress} in progress"

    async def _spend_line(self) -> str:
        metrics = await self.state_manager.get_metrics()
        today_cost = metrics.get("total_cost", 0.0)
        return f"Today spend : ${today_cost:.2f} / ${settings.max_daily_cost:.2f} budget"

    def _agents_block(self) -> str:
        newsletter = "  Newsletter     ✅"
        if settings.github_token and settings.enable_github_agent:
            github = f"  GitHub Monitor ✅ ({settings.github_repo})"
        else:
            github = "  GitHub Monitor ⏸️  (set GITHUB_TOKEN + ENABLE_GITHUB_AGENT=true)"
        telegram = "  Telegram       ✅"
        return f"{newsletter}\n{github}\n{telegram}"

    def _current_branch(self) -> str:
        try:
            return subprocess.check_output(
                ["git", "branch", "--show-current"],
                cwd=str(settings.github_repo_path),
                text=True,
                timeout=5,
            ).strip()
        except Exception:
            return "unknown"
