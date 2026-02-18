"""GitHub monitor: polls PRs and dispatches to workers."""

from typing import Any

from src.agents.base import AgentLoop
from src.config.settings import settings
from src.core.state_manager import StateManager
from src.github.client import GitHubClient
from src.github.types import PREvent, PRSnapshot, WorkerResult
from src.github.workers.ci_fixer import CIFixer
from src.github.workers.code_reviewer import CodeReviewer
from src.github.workers.pr_describer import PRDescriber
from src.utils.logger import get_logger

logger = get_logger("github.monitor")


class GitHubMonitor(AgentLoop):
    def __init__(self, state_manager: StateManager, github_client: GitHubClient) -> None:
        self._client = github_client
        self._state_manager = state_manager
        repo_path = settings.github_repo_path
        max_fix = settings.max_fix_attempts
        self._workers: dict[str, Any] = {
            "needs_description": PRDescriber(client=github_client),
            "ci_failure": CIFixer(
                client=github_client,
                state_manager=state_manager,
                repo_path=repo_path,
                max_fix_attempts=max_fix,
            ),
            "needs_review": CodeReviewer(client=github_client),
        }

    async def poll(self) -> list[PRSnapshot]:
        """Fetch all open PRs and their check runs."""
        prs = await self._client.list_open_prs()
        snapshots = []
        for pr in prs:
            check_runs = await self._client.get_check_runs(pr["head"]["sha"])
            snapshot = PRSnapshot(
                pr_number=pr["number"],
                head_sha=pr["head"]["sha"],
                title=pr["title"],
                body=pr.get("body") or "",
                author=pr["user"]["login"],
                branch=pr["head"]["ref"],
                check_runs=check_runs,
            )
            snapshots.append(snapshot)
        return snapshots

    async def triage(self, snapshots: list[PRSnapshot]) -> list[PREvent]:
        """Determine which PRs need action. Skip already-processed events."""
        events = []
        for snapshot in snapshots:
            if snapshot.needs_description:
                event_type = "needs_description"
            elif snapshot.ci_state in (
                "lint_fail",
                "test_fail",
                "secret_fail",
                "mixed_fail",
            ):
                event_type = "ci_failure"
            elif snapshot.ci_state == "all_pass":
                event_type = "needs_review"
            else:
                continue  # pending or nothing to do

            already_done = await self._state_manager.is_github_event_processed(
                snapshot.pr_number, snapshot.head_sha, event_type
            )
            if already_done:
                continue

            events.append(
                PREvent(
                    pr_number=snapshot.pr_number,
                    head_sha=snapshot.head_sha,
                    event_type=event_type,
                    snapshot=snapshot,
                )
            )
        return events

    async def act(self, events: list[PREvent]) -> list[WorkerResult]:
        """Dispatch each event to the appropriate worker."""
        results = []
        for event in events:
            worker = self._workers.get(event.event_type)
            if not worker:
                continue
            try:
                result = await worker.run(event.snapshot)
                results.append(result)
            except Exception as e:
                logger.error(
                    "worker_exception",
                    event_type=event.event_type,
                    pr=event.pr_number,
                    error=str(e),
                )
                results.append(
                    WorkerResult(
                        pr_number=event.pr_number,
                        head_sha=event.head_sha,
                        event_type=event.event_type,
                        action_taken="exception",
                        success=False,
                        error=str(e),
                    )
                )
        return results

    async def record(self, results: list[WorkerResult]) -> None:
        """Persist results to the database."""
        for result in results:
            if result.success:
                await self._state_manager.record_github_event(
                    pr_number=result.pr_number,
                    head_sha=result.head_sha,
                    event_type=result.event_type,
                    action_taken=result.action_taken,
                )
            logger.info(
                "github_event_recorded",
                pr=result.pr_number,
                event_type=result.event_type,
                success=result.success,
                action=result.action_taken,
            )
