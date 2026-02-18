"""
Unit tests for newsletter publishers.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from src.models.newsletter import Newsletter, NewsletterItem
from src.publishing.discord_publisher import DiscordPublisher
from src.publishing.markdown_publisher import MarkdownPublisher


@pytest.fixture
def sample_newsletter():
    """Sample newsletter for testing publishers."""
    items = [
        NewsletterItem(
            title="Novel LLM Architecture",
            url="https://arxiv.org/abs/2024.12345",
            summary="Researchers propose a new transformer architecture.",
            category="research",
            source="arxiv",
            relevance_score=9,
        ),
        NewsletterItem(
            title="OpenAI Releases GPT-5",
            url="https://openai.com/gpt5",
            summary="Major update with multimodal capabilities.",
            category="product",
            source="news",
            relevance_score=10,
        ),
    ]

    return Newsletter(
        date="2026-02-15-10", items=items, summary="Today's top AI updates", item_count=2
    )


@pytest.mark.unit
@pytest.mark.asyncio
class TestMarkdownPublisher:
    """Tests for MarkdownPublisher."""

    async def test_format_content_success(self, sample_newsletter):
        """Test that format_content returns markdown string."""
        publisher = MarkdownPublisher()
        result = await publisher.format_content(sample_newsletter)

        assert isinstance(result, str)
        assert "# AI Newsletter" in result
        assert "Novel LLM Architecture" in result

    async def test_publish_creates_file(self, sample_newsletter, tmp_path):
        """Test that publish creates a markdown file."""
        publisher = MarkdownPublisher()

        # Override output directory to use temp path
        publisher.output_dir = tmp_path

        formatted_content = await publisher.format_content(sample_newsletter)
        result = await publisher.publish(formatted_content, sample_newsletter)

        assert result.success is True
        assert "Published to" in result.message

        # Check file was created
        expected_file = tmp_path / "2026-02-15-10.md"
        assert expected_file.exists()

    async def test_publish_content_correctness(self, sample_newsletter, tmp_path):
        """Test that published file contains correct content."""
        publisher = MarkdownPublisher()
        publisher.output_dir = tmp_path

        formatted_content = await publisher.format_content(sample_newsletter)
        await publisher.publish(formatted_content, sample_newsletter)

        # Read and verify file content
        expected_file = tmp_path / "2026-02-15-10.md"
        content = expected_file.read_text(encoding="utf-8")

        assert "# AI Newsletter - 2026-02-15-10" in content
        assert "Novel LLM Architecture" in content
        assert "OpenAI Releases GPT-5" in content
        assert "Today's top AI updates" in content

    async def test_publish_handles_write_errors(self, sample_newsletter):
        """Test that publish handles write errors gracefully."""
        publisher = MarkdownPublisher()

        # Set output directory to invalid path
        publisher.output_dir = Path("/invalid/nonexistent/path")

        formatted_content = await publisher.format_content(sample_newsletter)
        result = await publisher.publish(formatted_content, sample_newsletter)

        assert result.success is False
        assert result.error is not None
        assert len(result.error) > 0

    async def test_publish_newsletter_end_to_end(self, sample_newsletter, tmp_path):
        """Test complete publish_newsletter workflow."""
        publisher = MarkdownPublisher()
        publisher.output_dir = tmp_path

        result = await publisher.publish_newsletter(sample_newsletter)

        assert result.success is True
        assert result.platform == "markdown"
        assert "filepath" in result.metadata
        assert "size" in result.metadata

        # Verify file exists
        expected_file = tmp_path / "2026-02-15-10.md"
        assert expected_file.exists()

    async def test_publish_metadata(self, sample_newsletter, tmp_path):
        """Test that publish result includes correct metadata."""
        publisher = MarkdownPublisher()
        publisher.output_dir = tmp_path

        formatted_content = await publisher.format_content(sample_newsletter)
        result = await publisher.publish(formatted_content, sample_newsletter)

        assert "filepath" in result.metadata
        assert "size" in result.metadata
        assert "filename" in result.metadata
        assert result.metadata["filename"] == "2026-02-15-10.md"
        assert result.metadata["size"] > 0


@pytest.mark.unit
@pytest.mark.asyncio
class TestDiscordPublisher:
    """Tests for DiscordPublisher."""

    async def test_format_content_returns_dict(self, sample_newsletter):
        """Test that format_content returns a dictionary."""
        publisher = DiscordPublisher()
        result = await publisher.format_content(sample_newsletter)

        assert isinstance(result, dict)
        assert "embeds" in result
        assert "username" in result

    async def test_validate_credentials_with_valid_webhook(self):
        """Test credential validation with valid webhook URL."""
        publisher = DiscordPublisher()
        publisher.webhook_url = "https://discord.com/api/webhooks/123/abc"

        assert publisher.validate_credentials() is True

    async def test_validate_credentials_with_invalid_webhook(self):
        """Test credential validation with invalid webhook URL."""
        publisher = DiscordPublisher()

        # Test various invalid cases
        publisher.webhook_url = None
        assert publisher.validate_credentials() is False

        publisher.webhook_url = ""
        assert publisher.validate_credentials() is False

        publisher.webhook_url = "http://discord.com/webhook"  # Not HTTPS
        assert publisher.validate_credentials() is False

    async def test_publish_fails_without_credentials(self, sample_newsletter):
        """Test that publish fails when credentials are not configured."""
        publisher = DiscordPublisher()
        publisher.webhook_url = None

        content = await publisher.format_content(sample_newsletter)
        result = await publisher.publish(content)

        assert result.success is False
        assert "not configured" in result.error

    @patch("httpx.AsyncClient")
    async def test_publish_success_with_valid_webhook(self, mock_client, sample_newsletter):
        """Test successful publish to Discord."""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.raise_for_status = Mock()

        mock_post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        publisher = DiscordPublisher()
        publisher.webhook_url = "https://discord.com/api/webhooks/123/abc"

        content = await publisher.format_content(sample_newsletter)
        result = await publisher.publish(content)

        assert result.success is True
        assert result.platform == "discord"
        assert "status_code" in result.metadata
        assert result.metadata["status_code"] == 204

        # Verify webhook was called
        mock_post.assert_called_once()

    @patch("httpx.AsyncClient")
    async def test_publish_handles_http_errors(self, mock_client, sample_newsletter):
        """Test that publish handles HTTP errors gracefully."""
        # Mock HTTP error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        mock_post = AsyncMock(
            side_effect=httpx.HTTPStatusError("Bad Request", request=Mock(), response=mock_response)
        )
        mock_client.return_value.__aenter__.return_value.post = mock_post

        publisher = DiscordPublisher()
        publisher.webhook_url = "https://discord.com/api/webhooks/123/abc"

        content = await publisher.format_content(sample_newsletter)
        result = await publisher.publish(content)

        assert result.success is False
        assert "HTTP 400" in result.error
        assert "Bad Request" in result.error

    @patch("httpx.AsyncClient")
    async def test_publish_handles_timeout(self, mock_client, sample_newsletter):
        """Test that publish handles timeout errors."""
        # Mock timeout exception
        mock_post = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
        mock_client.return_value.__aenter__.return_value.post = mock_post

        publisher = DiscordPublisher()
        publisher.webhook_url = "https://discord.com/api/webhooks/123/abc"

        content = await publisher.format_content(sample_newsletter)
        result = await publisher.publish(content)

        assert result.success is False
        assert "timeout" in result.error.lower()

    @patch("httpx.AsyncClient")
    async def test_publish_handles_network_errors(self, mock_client, sample_newsletter):
        """Test that publish handles general network errors."""
        # Mock network exception
        mock_post = AsyncMock(side_effect=Exception("Network error"))
        mock_client.return_value.__aenter__.return_value.post = mock_post

        publisher = DiscordPublisher()
        publisher.webhook_url = "https://discord.com/api/webhooks/123/abc"

        content = await publisher.format_content(sample_newsletter)
        result = await publisher.publish(content)

        assert result.success is False
        assert "Network error" in result.error

    @patch("httpx.AsyncClient")
    async def test_publish_newsletter_end_to_end(self, mock_client, sample_newsletter):
        """Test complete publish_newsletter workflow."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.raise_for_status = Mock()

        mock_post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        publisher = DiscordPublisher()
        publisher.webhook_url = "https://discord.com/api/webhooks/123/abc"

        result = await publisher.publish_newsletter(sample_newsletter)

        assert result.success is True
        assert result.platform == "discord"
        assert result.message == "Published to Discord"
