"""Code Reviewer worker: posts code review on PRs with green CI."""

import anthropic

from src.github.client import GitHubClient
from src.github.types import PRSnapshot, WorkerResult
from src.utils.logger import get_logger

try:
    from src.config.constants import MAX_DIFF_CHARS
except ImportError:
    MAX_DIFF_CHARS = 8_000

logger = get_logger("github.workers.code_reviewer")

SONNET_MODEL = "claude-sonnet-4-6"
REVIEW_MARKER = "<!-- elvagent-review -->"


class CodeReviewer:
    def __init__(self, client: GitHubClient) -> None:
        self._client = client
        self._anthropic = anthropic.AsyncAnthropic()

    async def _already_reviewed(self, pr_number: int) -> bool:
        """Check if we already posted a review (stateless -- checks GitHub API)."""
        reviews = await self._client.list_pr_reviews(pr_number)
        return any(REVIEW_MARKER in (r.get("body") or "") for r in reviews)

    async def run(self, snapshot: PRSnapshot) -> WorkerResult:
        """Post a code review on a PR with green CI."""
        try:
            if await self._already_reviewed(snapshot.pr_number):
                logger.info("pr_already_reviewed", pr=snapshot.pr_number)
                return WorkerResult(
                    pr_number=snapshot.pr_number,
                    head_sha=snapshot.head_sha,
                    event_type="needs_review",
                    action_taken="already_reviewed",
                    success=True,
                )

            prompt = (
                f"Review this GitHub PR:\nTitle: {snapshot.title}\n"
                f"Branch: {snapshot.branch}\nAuthor: {snapshot.author}\n\n"
                "Provide a constructive code review. Focus on: correctness, "
                "potential bugs, code quality, and any security concerns. "
                "Be concise (under 300 words)."
            )
            response = await self._anthropic.messages.create(
                model=SONNET_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            review_body = f"{REVIEW_MARKER}\n\n{response.content[0].text.strip()}"
            await self._client.create_pr_review(
                snapshot.pr_number, body=review_body, event="COMMENT"
            )

            logger.info("pr_review_posted", pr=snapshot.pr_number)
            return WorkerResult(
                pr_number=snapshot.pr_number,
                head_sha=snapshot.head_sha,
                event_type="needs_review",
                action_taken="review_posted",
                success=True,
            )
        except Exception as e:
            logger.error("code_reviewer_failed", pr=snapshot.pr_number, error=str(e))
            return WorkerResult(
                pr_number=snapshot.pr_number,
                head_sha=snapshot.head_sha,
                event_type="needs_review",
                action_taken="failed",
                success=False,
                error=str(e),
            )
