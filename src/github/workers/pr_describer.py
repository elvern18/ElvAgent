"""PR Describer worker: generates PR descriptions using Claude Haiku."""

import anthropic

from src.github.client import GitHubClient
from src.github.types import PRSnapshot, WorkerResult
from src.utils.logger import get_logger

try:
    from src.config.constants import MAX_DIFF_CHARS, PR_DESCRIPTION_SENTINEL
except ImportError:
    PR_DESCRIPTION_SENTINEL = "<!-- auto-generated -->"
    MAX_DIFF_CHARS = 8_000

logger = get_logger("github.workers.pr_describer")

HAIKU_MODEL = "claude-haiku-4-5-20251001"


class PRDescriber:
    def __init__(self, client: GitHubClient) -> None:
        self._client = client
        self._anthropic = anthropic.AsyncAnthropic()

    async def run(self, snapshot: PRSnapshot) -> WorkerResult:
        """Generate and update PR description."""
        try:
            prompt = (
                f"Write a concise GitHub PR description for a PR titled '{snapshot.title}' "
                f"on branch '{snapshot.branch}' by '{snapshot.author}'. "
                "Include sections: ## Summary, ## Changes, ## Testing. "
                "Keep it under 500 words. Return only the markdown content, no preamble."
            )
            response = await self._anthropic.messages.create(
                model=HAIKU_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            generated = response.content[0].text.strip()
            body = f"{PR_DESCRIPTION_SENTINEL}\n\n{generated}"
            await self._client.update_pr_body(snapshot.pr_number, body)

            logger.info("pr_description_generated", pr=snapshot.pr_number)
            return WorkerResult(
                pr_number=snapshot.pr_number,
                head_sha=snapshot.head_sha,
                event_type="needs_description",
                action_taken="description_generated",
                success=True,
            )
        except Exception as e:
            logger.error("pr_describer_failed", pr=snapshot.pr_number, error=str(e))
            return WorkerResult(
                pr_number=snapshot.pr_number,
                head_sha=snapshot.head_sha,
                event_type="needs_description",
                action_taken="failed",
                success=False,
                error=str(e),
            )
