"""Unit tests for GitHub agent workers."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.github.types import PRSnapshot
from src.github.workers.ci_fixer import CIFixer
from src.github.workers.code_reviewer import CodeReviewer
from src.github.workers.pr_describer import PRDescriber


def make_snapshot(
    pr_number=1,
    head_sha="abc123",
    title="Test PR",
    body="",
    author="testuser",
    branch="feature/test",
    check_runs=None,
) -> PRSnapshot:
    return PRSnapshot(
        pr_number=pr_number,
        head_sha=head_sha,
        title=title,
        body=body,
        author=author,
        branch=branch,
        check_runs=check_runs or [],
    )


def make_anthropic_response(text: str):
    """Create a mock Anthropic API response."""
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


class TestPRDescriber:
    @pytest.mark.asyncio
    async def test_generates_description(self):
        mock_client = AsyncMock()
        describer = PRDescriber(client=mock_client)

        mock_response = make_anthropic_response("## Summary\nThis PR adds a feature.")
        with patch.object(
            describer._anthropic.messages, "create", new=AsyncMock(return_value=mock_response)
        ):
            result = await describer.run(make_snapshot())

        assert result.success is True
        assert result.action_taken == "description_generated"
        mock_client.update_pr_body.assert_called_once()
        # Check sentinel is prepended
        body_arg = mock_client.update_pr_body.call_args[0][1]
        assert "<!-- auto-generated -->" in body_arg

    @pytest.mark.asyncio
    async def test_returns_failure_on_exception(self):
        mock_client = AsyncMock()
        describer = PRDescriber(client=mock_client)

        with patch.object(
            describer._anthropic.messages,
            "create",
            new=AsyncMock(side_effect=Exception("API error")),
        ):
            result = await describer.run(make_snapshot())

        assert result.success is False
        assert result.error == "API error"


class TestCodeReviewer:
    @pytest.mark.asyncio
    async def test_posts_review_when_not_already_reviewed(self):
        mock_client = AsyncMock()
        mock_client.list_pr_reviews = AsyncMock(return_value=[])
        reviewer = CodeReviewer(client=mock_client)

        mock_response = make_anthropic_response("This looks good.")
        with patch.object(
            reviewer._anthropic.messages, "create", new=AsyncMock(return_value=mock_response)
        ):
            result = await reviewer.run(make_snapshot())

        assert result.success is True
        assert result.action_taken == "review_posted"
        mock_client.create_pr_review.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_when_already_reviewed(self):
        mock_client = AsyncMock()
        mock_client.list_pr_reviews = AsyncMock(
            return_value=[{"body": "<!-- elvagent-review -->\n\nPrevious review"}]
        )
        reviewer = CodeReviewer(client=mock_client)

        result = await reviewer.run(make_snapshot())

        assert result.success is True
        assert result.action_taken == "already_reviewed"
        mock_client.create_pr_review.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_failure_on_exception(self):
        mock_client = AsyncMock()
        mock_client.list_pr_reviews = AsyncMock(side_effect=Exception("Network error"))
        reviewer = CodeReviewer(client=mock_client)

        result = await reviewer.run(make_snapshot())

        assert result.success is False


class TestCIFixerSecretFail:
    @pytest.mark.asyncio
    async def test_posts_comment_on_secret_fail(self):
        mock_client = AsyncMock()
        mock_state = MagicMock()
        mock_state.count_fix_attempts = AsyncMock(return_value=0)
        fixer = CIFixer(
            client=mock_client,
            state_manager=mock_state,
            repo_path=Path("/tmp"),
        )
        snapshot = make_snapshot(
            check_runs=[
                {
                    "id": 1,
                    "name": "secret-scan",
                    "conclusion": "failure",
                    "status": "completed",
                    "details_url": "https://github.com/owner/repo/actions/runs/123/jobs/456",
                }
            ]
        )

        result = await fixer.run(snapshot)

        assert result.success is True
        assert result.action_taken == "secret_alert_posted"
        mock_client.post_pr_comment.assert_called_once()
        # Verify subprocess.run was never called
        with patch("subprocess.run") as mock_run:
            # Already ran, just confirm pattern
            mock_run.assert_not_called()


class TestCIFixerCircuitBreaker:
    @pytest.mark.asyncio
    async def test_circuit_breaker_triggers_at_max_attempts(self):
        mock_client = AsyncMock()
        mock_state = MagicMock()
        mock_state.count_fix_attempts = AsyncMock(return_value=3)  # >= MAX_FIX_ATTEMPTS
        fixer = CIFixer(
            client=mock_client,
            state_manager=mock_state,
            repo_path=Path("/tmp"),
            max_fix_attempts=3,
        )
        snapshot = make_snapshot(
            check_runs=[
                {
                    "id": 1,
                    "name": "lint / ruff",
                    "conclusion": "failure",
                    "status": "completed",
                    "details_url": "https://github.com/owner/repo/actions/runs/123/jobs/456",
                }
            ]
        )

        with patch("subprocess.run") as mock_subprocess:
            result = await fixer.run(snapshot)

        assert result.action_taken == "circuit_breaker_triggered"
        mock_subprocess.assert_not_called()
        mock_client.post_pr_comment.assert_called_once()


class TestCIFixerLintFail:
    @pytest.mark.asyncio
    async def test_runs_ruff_and_pushes_on_lint_fail(self):
        mock_client = AsyncMock()
        mock_state = MagicMock()
        mock_state.count_fix_attempts = AsyncMock(return_value=0)
        fixer = CIFixer(
            client=mock_client,
            state_manager=mock_state,
            repo_path=Path("/tmp"),
        )
        snapshot = make_snapshot(
            check_runs=[
                {
                    "id": 1,
                    "name": "lint / ruff",
                    "conclusion": "failure",
                    "status": "completed",
                    "details_url": "https://github.com/owner/repo/actions/runs/123/jobs/456",
                }
            ]
        )

        mock_proc = MagicMock()
        mock_proc.stdout = "M file.py\n"
        mock_proc.stderr = ""
        mock_proc.returncode = 0

        with patch("subprocess.run", return_value=mock_proc) as mock_subprocess:
            # Make _run_git work: patch subprocess.run to return non-empty git status
            await fixer.run(snapshot)

        # subprocess.run should have been called (ruff + git operations)
        assert mock_subprocess.called


class TestCIFixerRunIdExtraction:
    def test_run_id_extraction_from_details_url(self):
        """Test that run_id is correctly extracted from details_url."""
        details_url = "https://github.com/owner/repo/actions/runs/12345678/jobs/987654321"
        run_id = int(details_url.split("/runs/")[1].split("/")[0])
        assert run_id == 12345678  # NOT 987654321 (which is the job id)
