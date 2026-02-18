"""Unit tests for GitHubMonitor and PRSnapshot."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.github.monitor import GitHubMonitor
from src.github.types import PRSnapshot, WorkerResult


def make_snapshot(check_runs=None, body="") -> PRSnapshot:
    return PRSnapshot(
        pr_number=1,
        head_sha="abc123",
        title="Test PR",
        body=body,
        author="testuser",
        branch="feature/test",
        check_runs=check_runs or [],
    )


def make_check_run(name: str, conclusion: str | None, status: str = "completed") -> dict:
    return {
        "id": 1,
        "name": name,
        "conclusion": conclusion,
        "status": status,
        "details_url": "https://github.com/owner/repo/actions/runs/12345/jobs/67890",
    }


class TestPRSnapshotCiState:
    def test_all_pass_when_no_check_runs(self):
        s = make_snapshot([])
        assert s.ci_state == "all_pass"

    def test_all_pass_when_all_success(self):
        s = make_snapshot(
            [
                make_check_run("lint", "success"),
                make_check_run("tests", "success"),
            ]
        )
        assert s.ci_state == "all_pass"

    def test_secret_fail_priority(self):
        s = make_snapshot(
            [
                make_check_run("secret-scan", "failure"),
                make_check_run("lint", "failure"),
            ]
        )
        assert s.ci_state == "secret_fail"

    def test_lint_fail_only(self):
        s = make_snapshot(
            [
                make_check_run("lint / ruff", "failure"),
                make_check_run("tests", "success"),
            ]
        )
        assert s.ci_state == "lint_fail"

    def test_test_fail_only(self):
        s = make_snapshot(
            [
                make_check_run("unit-tests", "failure"),
                make_check_run("lint", "success"),
            ]
        )
        assert s.ci_state == "test_fail"

    def test_mixed_fail(self):
        s = make_snapshot(
            [
                make_check_run("lint", "failure"),
                make_check_run("unit-tests", "failure"),
            ]
        )
        assert s.ci_state == "mixed_fail"

    def test_pending_when_in_progress(self):
        s = make_snapshot(
            [
                make_check_run("lint", None, status="in_progress"),
            ]
        )
        assert s.ci_state == "pending"

    def test_pending_when_queued(self):
        s = make_snapshot(
            [
                make_check_run("tests", None, status="queued"),
            ]
        )
        assert s.ci_state == "pending"


class TestPRSnapshotNeedsDescription:
    def test_needs_description_when_sentinel_present(self):
        s = make_snapshot(body="<!-- auto-generated -->")
        assert s.needs_description is True

    def test_no_description_needed_when_no_sentinel(self):
        s = make_snapshot(body="This is a real description")
        assert s.needs_description is False

    def test_no_description_needed_when_body_empty(self):
        s = make_snapshot(body="")
        assert s.needs_description is False


class TestGitHubMonitorTriage:
    def _make_monitor(self):
        mock_state = MagicMock()
        mock_state.is_github_event_processed = AsyncMock(return_value=False)
        mock_client = MagicMock()
        monitor = GitHubMonitor.__new__(GitHubMonitor)
        monitor._client = mock_client
        monitor._state_manager = mock_state
        monitor._workers = {}
        return monitor, mock_state

    @pytest.mark.asyncio
    async def test_triage_skips_processed_events(self):
        monitor, mock_state = self._make_monitor()
        mock_state.is_github_event_processed = AsyncMock(return_value=True)
        snapshot = make_snapshot([make_check_run("lint", "failure")])
        events = await monitor.triage([snapshot])
        assert events == []

    @pytest.mark.asyncio
    async def test_triage_emits_needs_description(self):
        monitor, mock_state = self._make_monitor()
        snapshot = make_snapshot(body="<!-- auto-generated -->")
        events = await monitor.triage([snapshot])
        assert len(events) == 1
        assert events[0].event_type == "needs_description"

    @pytest.mark.asyncio
    async def test_triage_emits_ci_failure(self):
        monitor, mock_state = self._make_monitor()
        snapshot = make_snapshot([make_check_run("lint / ruff", "failure")])
        events = await monitor.triage([snapshot])
        assert len(events) == 1
        assert events[0].event_type == "ci_failure"

    @pytest.mark.asyncio
    async def test_triage_emits_needs_review_on_all_pass(self):
        monitor, mock_state = self._make_monitor()
        snapshot = make_snapshot([make_check_run("lint", "success")])
        events = await monitor.triage([snapshot])
        assert len(events) == 1
        assert events[0].event_type == "needs_review"

    @pytest.mark.asyncio
    async def test_triage_skips_pending(self):
        monitor, mock_state = self._make_monitor()
        snapshot = make_snapshot([make_check_run("lint", None, status="in_progress")])
        events = await monitor.triage([snapshot])
        assert events == []


class TestGitHubMonitorRecord:
    @pytest.mark.asyncio
    async def test_record_calls_state_manager_on_success(self):
        mock_state = MagicMock()
        mock_state.record_github_event = AsyncMock()
        monitor = GitHubMonitor.__new__(GitHubMonitor)
        monitor._state_manager = mock_state
        monitor._workers = {}
        monitor._client = MagicMock()

        results = [
            WorkerResult(
                pr_number=1,
                head_sha="abc",
                event_type="needs_review",
                action_taken="review_posted",
                success=True,
            )
        ]
        await monitor.record(results)
        mock_state.record_github_event.assert_called_once_with(
            pr_number=1, head_sha="abc", event_type="needs_review", action_taken="review_posted"
        )

    @pytest.mark.asyncio
    async def test_record_skips_state_on_failure(self):
        mock_state = MagicMock()
        mock_state.record_github_event = AsyncMock()
        monitor = GitHubMonitor.__new__(GitHubMonitor)
        monitor._state_manager = mock_state
        monitor._workers = {}
        monitor._client = MagicMock()

        results = [
            WorkerResult(
                pr_number=1,
                head_sha="abc",
                event_type="ci_failure",
                action_taken="failed",
                success=False,
                error="oops",
            )
        ]
        await monitor.record(results)
        mock_state.record_github_event.assert_not_called()
