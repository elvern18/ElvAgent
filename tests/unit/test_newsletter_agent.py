"""
Unit tests for NewsletterAgent.

Mocks StateManager and Orchestrator so no real API calls are made.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.newsletter_agent import (
    NEWSLETTER_INTERVAL_MINUTES,
    NewsletterAgent,
    NewsletterEvent,
)
from src.core.orchestrator import CycleResult
from src.publishing.base import PublishResult


def _make_state_manager(minutes_since: float) -> MagicMock:
    sm = MagicMock()
    sm.minutes_since_last_newsletter = AsyncMock(return_value=minutes_since)
    return sm


def _make_cycle_result(success: bool = True) -> CycleResult:
    return CycleResult(
        success=success,
        newsletter=None,
        item_count=5,
        filtered_count=3,
        publish_results=[PublishResult(platform="telegram", success=True)],
        total_cost=0.035,
        error=None if success else "something went wrong",
    )


# ---------------------------------------------------------------------------
# poll
# ---------------------------------------------------------------------------


class TestPoll:
    async def test_returns_minutes_from_state_manager(self):
        agent = NewsletterAgent(state_manager=_make_state_manager(30.0))
        result = await agent.poll()
        assert result == [30.0]

    async def test_returns_large_number_for_first_run(self):
        agent = NewsletterAgent(state_manager=_make_state_manager(999_999.0))
        result = await agent.poll()
        assert result[0] == 999_999.0


# ---------------------------------------------------------------------------
# triage
# ---------------------------------------------------------------------------


class TestTriage:
    async def test_no_event_when_newsletter_recent(self):
        agent = NewsletterAgent(state_manager=_make_state_manager(30.0))
        events = await agent.triage([30.0])
        assert events == []

    async def test_event_when_exactly_at_threshold(self):
        agent = NewsletterAgent(state_manager=_make_state_manager(55.0))
        events = await agent.triage([float(NEWSLETTER_INTERVAL_MINUTES)])
        assert len(events) == 1
        assert events[0].triggered_by == "schedule"

    async def test_event_when_overdue(self):
        agent = NewsletterAgent(state_manager=_make_state_manager(120.0))
        events = await agent.triage([120.0])
        assert len(events) == 1
        assert events[0].minutes_since_last == 120.0

    async def test_event_on_first_run(self):
        agent = NewsletterAgent(state_manager=_make_state_manager(999_999.0))
        events = await agent.triage([999_999.0])
        assert len(events) == 1

    async def test_no_event_on_empty_snapshots(self):
        agent = NewsletterAgent(state_manager=_make_state_manager(999_999.0))
        events = await agent.triage([])
        assert events == []


# ---------------------------------------------------------------------------
# act
# ---------------------------------------------------------------------------


class TestAct:
    async def test_runs_orchestrator_for_each_event(self):
        sm = _make_state_manager(60.0)
        agent = NewsletterAgent(state_manager=sm)

        mock_result = _make_cycle_result(success=True)
        mock_orchestrator = MagicMock()
        mock_orchestrator.run_cycle = AsyncMock(return_value=mock_result)

        with (
            patch.object(agent, "_build_orchestrator", return_value=mock_orchestrator),
            patch("src.agents.newsletter_agent.settings") as mock_settings,
        ):
            mock_settings.validate_production_config.return_value = True
            events = [NewsletterEvent(triggered_by="schedule", minutes_since_last=60.0)]
            results = await agent.act(events)

        assert len(results) == 1
        assert results[0].success is True
        mock_orchestrator.run_cycle.assert_awaited_once_with(mode="production")

    async def test_skips_cycle_when_config_invalid(self):
        sm = _make_state_manager(60.0)
        agent = NewsletterAgent(state_manager=sm)

        with patch("src.agents.newsletter_agent.settings") as mock_settings:
            mock_settings.validate_production_config.return_value = False
            events = [NewsletterEvent(triggered_by="schedule", minutes_since_last=60.0)]
            results = await agent.act(events)

        assert results == []


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


class TestRecord:
    async def test_record_does_not_raise_on_success(self):
        agent = NewsletterAgent(state_manager=_make_state_manager(60.0))
        # Should complete without exception
        await agent.record([_make_cycle_result(success=True)])

    async def test_record_does_not_raise_on_failure(self):
        agent = NewsletterAgent(state_manager=_make_state_manager(60.0))
        await agent.record([_make_cycle_result(success=False)])
