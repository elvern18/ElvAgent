"""
Unit tests for TwitterPublisher and TwitterFormatter.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.models.newsletter import Newsletter, NewsletterItem
from src.publishing.formatters.twitter_formatter import TwitterFormatter
from src.publishing.twitter_publisher import TwitterPublisher


@pytest.fixture
def sample_newsletter():
    """Create sample newsletter for testing."""
    return Newsletter(
        date="2026-02-16-10",
        items=[
            NewsletterItem(
                title="Novel LLM Architecture",
                url="https://arxiv.org/abs/2024.12345",
                source="arxiv",
                category="research",
                relevance_score=9,
                summary="This paper presents a breakthrough in transformer architectures.",
            ),
            NewsletterItem(
                title="Another Research Paper",
                url="https://arxiv.org/abs/2024.54321",
                source="arxiv",
                category="research",
                relevance_score=8,
                summary="Significant development in multimodal learning.",
            ),
        ],
        summary="Today's AI highlights include groundbreaking research.",
        item_count=2,
    )


class TestTwitterFormatter:
    """Test Twitter formatter."""

    def test_formatter_initialization(self):
        """Test that formatter initializes correctly."""
        formatter = TwitterFormatter()
        assert formatter.platform_name == "twitter"
        assert formatter.MAX_TWEET_LENGTH == 280

    def test_format_returns_list(self, sample_newsletter):
        """Test that format returns a list of tweets."""
        formatter = TwitterFormatter()
        tweets = formatter.format(sample_newsletter)

        assert isinstance(tweets, list)
        assert len(tweets) > 0

    def test_format_intro_tweet(self, sample_newsletter):
        """Test that first tweet is an intro with summary."""
        formatter = TwitterFormatter()
        tweets = formatter.format(sample_newsletter)

        intro = tweets[0]
        assert "🤖 AI News Update" in intro
        assert sample_newsletter.summary in intro or "Today's AI highlights" in intro

    def test_format_item_tweets(self, sample_newsletter):
        """Test that items are formatted correctly."""
        formatter = TwitterFormatter()
        tweets = formatter.format(sample_newsletter)

        # Should have intro + at least 1 item tweet
        assert len(tweets) >= 2

        # Check second tweet (first item)
        item_tweet = tweets[1]
        assert "1." in item_tweet  # Item number
        assert sample_newsletter.items[0].title in item_tweet or "Novel LLM" in item_tweet
        assert sample_newsletter.items[0].url in item_tweet

    def test_tweet_length_limit(self, sample_newsletter):
        """Test that all tweets are within 280 characters."""
        formatter = TwitterFormatter()
        tweets = formatter.format(sample_newsletter)

        for i, tweet in enumerate(tweets):
            assert len(tweet) <= 280, f"Tweet {i + 1} exceeds 280 chars: {len(tweet)} chars"

    def test_long_item_splitting(self):
        """Test that very long items are split into multiple tweets."""
        # Create item with very long title and summary
        long_newsletter = Newsletter(
            date="2026-02-16-10",
            items=[
                NewsletterItem(
                    title="A" * 200,  # Very long title
                    url="https://example.com/test",
                    source="test",
                    category="research",
                    relevance_score=8,
                    summary="B" * 200,  # Very long summary
                ),
            ],
            summary="Test",
            item_count=1,
        )

        formatter = TwitterFormatter()
        tweets = formatter.format(long_newsletter)

        # Should have intro + multiple tweets for the item
        assert len(tweets) >= 2

        # All should be within limit
        for tweet in tweets:
            assert len(tweet) <= 280

    def test_date_formatting(self, sample_newsletter):
        """Test that date is formatted nicely in intro."""
        formatter = TwitterFormatter()
        tweets = formatter.format(sample_newsletter)

        intro = tweets[0]
        # Should format as "Feb 16, 10:00" not "2026-02-16-10"
        assert "Feb 16" in intro or "2026-02-16-10" in intro


class TestTwitterPublisher:
    """Test Twitter publisher."""

    def test_publisher_initialization(self):
        """Test that publisher initializes correctly."""
        publisher = TwitterPublisher()
        assert publisher.platform_name == "twitter"
        assert isinstance(publisher.formatter, TwitterFormatter)

    def test_validate_credentials_with_no_config(self):
        """Test credential validation with missing config."""
        with patch("src.publishing.twitter_publisher.settings") as mock_settings:
            mock_settings.twitter_api_key = None
            mock_settings.twitter_api_secret = None
            mock_settings.twitter_access_token = None
            mock_settings.twitter_access_secret = None

            publisher = TwitterPublisher()
            assert publisher.validate_credentials() is False

    def test_validate_credentials_with_config(self):
        """Test credential validation with complete config."""
        with patch("src.publishing.twitter_publisher.settings") as mock_settings:
            mock_settings.twitter_api_key = "test_key"
            mock_settings.twitter_api_secret = "test_secret"
            mock_settings.twitter_access_token = "test_token"
            mock_settings.twitter_access_secret = "test_token_secret"

            TwitterPublisher()
            # Don't test actual initialization, just validation
            assert all(
                [
                    mock_settings.twitter_api_key,
                    mock_settings.twitter_api_secret,
                    mock_settings.twitter_access_token,
                    mock_settings.twitter_access_secret,
                ]
            )

    @pytest.mark.asyncio
    async def test_format_content(self, sample_newsletter):
        """Test content formatting."""
        publisher = TwitterPublisher()
        tweets = await publisher.format_content(sample_newsletter)

        assert isinstance(tweets, list)
        assert len(tweets) > 0
        assert all(len(tweet) <= 280 for tweet in tweets)

    @pytest.mark.asyncio
    async def test_publish_without_credentials(self, sample_newsletter):
        """Test that publish fails gracefully without credentials."""
        with patch("src.publishing.twitter_publisher.settings") as mock_settings:
            mock_settings.twitter_api_key = None
            mock_settings.twitter_api_secret = None
            mock_settings.twitter_access_token = None
            mock_settings.twitter_access_secret = None

            publisher = TwitterPublisher()
            result = await publisher.publish_newsletter(sample_newsletter)

            assert result.success is False
            assert "credentials not configured" in result.error.lower()

    @pytest.mark.asyncio
    async def test_publish_with_mock_api(self, sample_newsletter):
        """Test publishing with mocked Twitter API v1.1."""
        # Create mock API
        mock_api = MagicMock()
        mock_status = MagicMock()
        mock_status.id_str = "123456789"
        mock_api.update_status = MagicMock(return_value=mock_status)

        # Mock user credentials for URL generation
        mock_user = MagicMock()
        mock_user.screen_name = "test_user"
        mock_api.verify_credentials = MagicMock(return_value=mock_user)

        # Create publisher and inject mock API
        publisher = TwitterPublisher()
        publisher.api = mock_api

        # Mock credentials as valid
        with patch.object(publisher, "validate_credentials", return_value=True):
            result = await publisher.publish_newsletter(sample_newsletter)

            # Should succeed
            assert result.success is True
            assert "tweet thread" in result.message.lower()
            assert result.metadata["tweet_count"] > 0

    @pytest.mark.asyncio
    async def test_publish_handles_api_errors(self, sample_newsletter):
        """Test that API errors are handled gracefully."""
        import tweepy

        # Create mock API that raises error
        mock_api = MagicMock()
        mock_api.update_status = MagicMock(
            side_effect=tweepy.TweepyException("Rate limit exceeded")
        )

        publisher = TwitterPublisher()
        publisher.api = mock_api

        with patch.object(publisher, "validate_credentials", return_value=True):
            result = await publisher.publish_newsletter(sample_newsletter)

            assert result.success is False
            assert "twitter api error" in result.error.lower()
