"""
AgentLoop abstract base class.
Provides the ReAct (Reason → Act) loop: poll → triage → act → record.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from src.utils.logger import get_logger

logger = get_logger("agent.base")


class AgentLoop(ABC):
    """
    Abstract base class for all autonomous agents.

    Subclasses implement four abstract methods that form the ReAct loop:
      poll()   → observe the world (returns observations)
      triage() → reason: which observations need action?
      act()    → act: fan-out to workers
      record() → persist outcomes to durable storage
    """

    @abstractmethod
    async def poll(self) -> list[Any]:
        """
        Observe the world and return a list of snapshots.

        Returns:
            List of snapshot objects (type defined by subclass)
        """

    @abstractmethod
    async def triage(self, snapshots: list[Any]) -> list[Any]:
        """
        Reason about snapshots and return events that require action.

        Args:
            snapshots: Raw observations from poll()

        Returns:
            List of event objects (type defined by subclass)
        """

    @abstractmethod
    async def act(self, events: list[Any]) -> list[Any]:
        """
        Execute actions for each event and return results.

        Args:
            events: Events requiring action from triage()

        Returns:
            List of result objects (type defined by subclass)
        """

    @abstractmethod
    async def record(self, results: list[Any]) -> None:
        """
        Persist outcomes to durable storage.

        Args:
            results: Worker results from act()
        """

    async def run_cycle(self) -> None:
        """
        Execute one full ReAct cycle: poll → triage → act → record.

        Returns early (no act/record) when triage returns an empty list.
        """
        logger.info("agent_cycle_start", agent=type(self).__name__)

        snapshots = await self.poll()
        logger.info("agent_polled", agent=type(self).__name__, snapshots=len(snapshots))

        events = await self.triage(snapshots)
        logger.info("agent_triaged", agent=type(self).__name__, events=len(events))

        if not events:
            logger.info("agent_cycle_no_events", agent=type(self).__name__)
            return

        results = await self.act(events)
        logger.info("agent_acted", agent=type(self).__name__, results=len(results))

        await self.record(results)
        logger.info("agent_cycle_complete", agent=type(self).__name__)

    async def run_forever(self, interval_seconds: int = 60, max_cycles: int = 0) -> None:
        """
        Run run_cycle() in a loop, sleeping interval_seconds between cycles.

        Cycle-level exceptions are caught and logged — the loop never crashes.

        Args:
            interval_seconds: Seconds to sleep between cycles
            max_cycles: Maximum cycles to run (0 = infinite)
        """
        logger.info(
            "agent_loop_started",
            agent=type(self).__name__,
            interval_seconds=interval_seconds,
            max_cycles=max_cycles if max_cycles > 0 else "infinite",
        )

        cycles_run = 0
        while True:
            try:
                await self.run_cycle()
            except Exception as e:
                logger.error(
                    "agent_cycle_error",
                    agent=type(self).__name__,
                    error=str(e),
                    error_type=type(e).__name__,
                )

            cycles_run += 1
            if max_cycles > 0 and cycles_run >= max_cycles:
                logger.info("agent_loop_finished", agent=type(self).__name__, cycles=cycles_run)
                return

            await asyncio.sleep(interval_seconds)
