"""
MasterAgent — runs all sub-agents concurrently in one asyncio event loop.

Manages:
  - NewsletterAgent : hourly newsletter publishing (always on)
  - GitHubMonitor   : PR management (requires GITHUB_TOKEN + enable_github_agent)
  - TaskWorker      : processes task queue from Telegram etc. (Phase B)
  - TelegramAgent   : handles incoming Telegram DMs (Phase B)

A crash inside any single agent is caught and logged; the others continue.
Responds to SIGTERM / SIGINT for graceful shutdown.
"""

import asyncio
import signal
from collections.abc import Coroutine
from typing import Any

from src.config.settings import settings
from src.core.state_manager import StateManager
from src.utils.logger import get_logger

logger = get_logger("master_agent")


class MasterAgent:
    """
    Top-level coordinator that runs all sub-agents as concurrent coroutines.

    Usage:
        master = MasterAgent()
        await master.run_forever()
    """

    def __init__(self):
        self.state_manager = StateManager()
        from src.memory.memory_store import MemoryStore

        self.memory_store = MemoryStore()

    async def run_forever(self) -> None:
        """Initialise DB, register signal handlers, then run all agents."""
        await self.state_manager.init_db()
        logger.info("master_agent_starting")

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_shutdown_signal)

        coroutines = self._build_agent_coroutines()
        logger.info("master_agent_started", agents=len(coroutines))

        # return_exceptions=True: one agent crash doesn't cancel the rest
        results = await asyncio.gather(*coroutines, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("agent_coroutine_failed", index=i, error=str(result))

        logger.info("master_agent_stopped")

    def _handle_shutdown_signal(self) -> None:
        """Cancel all running tasks on SIGTERM / SIGINT."""
        logger.info("master_agent_shutdown_requested")
        for task in asyncio.all_tasks():
            task.cancel()

    def _build_agent_coroutines(self) -> list[Coroutine[Any, Any, None]]:
        """Return the list of agent coroutines to run concurrently."""
        coroutines: list[Coroutine[Any, Any, None]] = []

        # --- Newsletter agent (always on) ---
        from src.agents.newsletter_agent import NewsletterAgent

        newsletter_agent = NewsletterAgent(state_manager=self.state_manager)
        coroutines.append(newsletter_agent.run_forever(interval_seconds=60))
        logger.info("newsletter_agent_registered")

        # --- GitHub monitor (optional) ---
        if settings.github_token and settings.enable_github_agent:
            from src.github.client import GitHubClient
            from src.github.monitor import GitHubMonitor

            github_client = GitHubClient(token=settings.github_token, repo=settings.github_repo)
            github_monitor = GitHubMonitor(
                state_manager=self.state_manager, github_client=github_client
            )
            coroutines.append(
                github_monitor.run_forever(interval_seconds=settings.github_poll_interval)
            )
            logger.info("github_monitor_registered", repo=settings.github_repo)
        else:
            logger.info(
                "github_monitor_skipped",
                reason="GITHUB_TOKEN not set or ENABLE_GITHUB_AGENT=false",
            )

        # --- Task worker (Phase B) ---
        try:
            from src.agents.task_worker import TaskWorker

            task_worker = TaskWorker(
                state_manager=self.state_manager, memory_store=self.memory_store
            )
            coroutines.append(task_worker.run_forever(interval_seconds=5))
            logger.info("task_worker_registered")
        except ImportError:
            logger.info("task_worker_not_available", note="will be added in Phase B")

        # --- Telegram command agent (Phase B) ---
        try:
            from src.agents.telegram_agent import TelegramAgent

            if settings.telegram_bot_token and settings.telegram_owner_id:
                telegram_agent = TelegramAgent(
                    state_manager=self.state_manager, memory_store=self.memory_store
                )
                coroutines.append(telegram_agent.run_forever())
                logger.info("telegram_agent_registered")
            else:
                logger.warning(
                    "telegram_agent_skipped",
                    reason="TELEGRAM_BOT_TOKEN or TELEGRAM_OWNER_ID not set",
                )
        except ImportError:
            logger.info("telegram_agent_not_available", note="will be added in Phase B")

        return coroutines
