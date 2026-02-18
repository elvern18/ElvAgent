"""GitHub REST API client wrapper."""

import httpx

from src.utils.logger import get_logger
from src.utils.rate_limiter import rate_limiter

logger = get_logger("github.client")

GITHUB_API_BASE = "https://api.github.com"


class GitHubClient:
    """Pure httpx REST wrapper for GitHub API. No business logic."""

    def __init__(self, token: str, repo: str) -> None:
        """Initialize GitHub client.

        Args:
            token: GitHub personal access token.
            repo: Repository in "owner/repo" format.
        """
        self._repo = repo
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _url(self, path: str) -> str:
        return f"{GITHUB_API_BASE}/repos/{self._repo}/{path.lstrip('/')}"

    async def list_open_prs(self) -> list[dict]:
        """GET /pulls?state=open&per_page=100"""
        await rate_limiter.acquire("github")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                self._url("pulls"),
                headers=self._headers,
                params={"state": "open", "per_page": 100},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_check_runs(self, head_sha: str) -> list[dict]:
        """GET /commits/{sha}/check-runs"""
        await rate_limiter.acquire("github")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                self._url(f"commits/{head_sha}/check-runs"),
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json().get("check_runs", [])

    async def get_pull_request(self, pr_number: int) -> dict:
        """GET /pulls/{number}"""
        await rate_limiter.acquire("github")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                self._url(f"pulls/{pr_number}"),
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def update_pr_body(self, pr_number: int, body: str) -> None:
        """PATCH /pulls/{number} with {"body": body}"""
        await rate_limiter.acquire("github")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.patch(
                self._url(f"pulls/{pr_number}"),
                headers=self._headers,
                json={"body": body},
            )
            resp.raise_for_status()

    async def post_pr_comment(self, pr_number: int, body: str) -> None:
        """POST /issues/{number}/comments with {"body": body}"""
        await rate_limiter.acquire("github")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self._url(f"issues/{pr_number}/comments"),
                headers=self._headers,
                json={"body": body},
            )
            resp.raise_for_status()

    async def create_pr_review(self, pr_number: int, body: str, event: str = "COMMENT") -> None:
        """POST /pulls/{number}/reviews with {"body": body, "event": event}"""
        await rate_limiter.acquire("github")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self._url(f"pulls/{pr_number}/reviews"),
                headers=self._headers,
                json={"body": body, "event": event},
            )
            resp.raise_for_status()

    async def list_pr_reviews(self, pr_number: int) -> list[dict]:
        """GET /pulls/{number}/reviews"""
        await rate_limiter.acquire("github")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                self._url(f"pulls/{pr_number}/reviews"),
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_workflow_run_logs(self, run_id: int) -> bytes:
        """GET /actions/runs/{run_id}/logs -- returns raw zip bytes."""
        await rate_limiter.acquire("github")
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                self._url(f"actions/runs/{run_id}/logs"),
                headers=self._headers,
                follow_redirects=True,
            )
            resp.raise_for_status()
            return resp.content

    async def list_check_annotations(self, check_run_id: int) -> list[dict]:
        """GET /check-runs/{check_run_id}/annotations"""
        await rate_limiter.acquire("github")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                self._url(f"check-runs/{check_run_id}/annotations"),
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()
