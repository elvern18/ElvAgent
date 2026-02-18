"""Unit tests for GitHubClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.github.client import GitHubClient

REPO = "owner/repo"
TOKEN = "ghp_test123"


@pytest.fixture
def client():
    return GitHubClient(token=TOKEN, repo=REPO)


def _make_mock_response(json_data, status_code=200):
    """Create a mock httpx response."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_data
    mock_resp.status_code = status_code
    mock_resp.content = b"zip_content"
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _make_async_client_mock(response):
    """Wrap a mock response in an async context manager."""
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=response)
    mock_http.patch = AsyncMock(return_value=response)
    mock_http.post = AsyncMock(return_value=response)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_http)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm, mock_http


class TestGitHubClientListOpenPRs:
    @pytest.mark.asyncio
    async def test_list_open_prs(self, client):
        prs = [{"number": 1, "head": {"sha": "abc123"}}]
        resp = _make_mock_response(prs)
        cm, mock_http = _make_async_client_mock(resp)
        with (
            patch("src.github.client.rate_limiter.acquire", new=AsyncMock()),
            patch("httpx.AsyncClient", return_value=cm),
        ):
            result = await client.list_open_prs()
        assert result == prs
        mock_http.get.assert_called_once()
        call_url = mock_http.get.call_args[0][0]
        assert "/pulls" in call_url


class TestGitHubClientGetCheckRuns:
    @pytest.mark.asyncio
    async def test_get_check_runs(self, client):
        sha = "abc123def456"
        check_runs_data = {"check_runs": [{"id": 1, "name": "lint", "conclusion": "failure"}]}
        resp = _make_mock_response(check_runs_data)
        cm, mock_http = _make_async_client_mock(resp)
        with (
            patch("src.github.client.rate_limiter.acquire", new=AsyncMock()),
            patch("httpx.AsyncClient", return_value=cm),
        ):
            result = await client.get_check_runs(sha)
        assert result == check_runs_data["check_runs"]


class TestGitHubClientUpdatePRBody:
    @pytest.mark.asyncio
    async def test_update_pr_body(self, client):
        resp = _make_mock_response({"number": 1})
        cm, mock_http = _make_async_client_mock(resp)
        with (
            patch("src.github.client.rate_limiter.acquire", new=AsyncMock()),
            patch("httpx.AsyncClient", return_value=cm),
        ):
            await client.update_pr_body(1, "New description")
        mock_http.patch.assert_called_once()


class TestGitHubClientPostPRComment:
    @pytest.mark.asyncio
    async def test_post_pr_comment(self, client):
        resp = _make_mock_response({"id": 42})
        cm, mock_http = _make_async_client_mock(resp)
        with (
            patch("src.github.client.rate_limiter.acquire", new=AsyncMock()),
            patch("httpx.AsyncClient", return_value=cm),
        ):
            await client.post_pr_comment(1, "Test comment")
        mock_http.post.assert_called_once()


class TestGitHubClientCreatePRReview:
    @pytest.mark.asyncio
    async def test_create_pr_review(self, client):
        resp = _make_mock_response({"id": 10})
        cm, mock_http = _make_async_client_mock(resp)
        with (
            patch("src.github.client.rate_limiter.acquire", new=AsyncMock()),
            patch("httpx.AsyncClient", return_value=cm),
        ):
            await client.create_pr_review(1, "Review body", event="COMMENT")
        mock_http.post.assert_called_once()


class TestGitHubClientGetWorkflowRunLogs:
    @pytest.mark.asyncio
    async def test_get_workflow_run_logs_returns_bytes(self, client):
        resp = _make_mock_response({})
        resp.content = b"PK\x03\x04..."  # zip bytes
        cm, mock_http = _make_async_client_mock(resp)
        with (
            patch("src.github.client.rate_limiter.acquire", new=AsyncMock()),
            patch("httpx.AsyncClient", return_value=cm),
        ):
            result = await client.get_workflow_run_logs(12345)
        assert isinstance(result, bytes)
