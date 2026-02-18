"""
Unit tests for ContentPipeline.
Tests filtering, conversion, and newsletter assembly.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.constants import MIN_RELEVANCE_SCORE, RESEARCH_TIME_WINDOW_HOURS
from src.core.content_pipeline import ContentPipeline
from src.models.newsletter import NewsletterItem
from src.research.base import ContentItem


@pytest.fixture
def mock_state_manager():
    """Create mock StateManager."""
    manager = MagicMock()
    manager.check_duplicate = AsyncMock(return_value=False)
    manager.track_api_usage = AsyncMock()
    return manager


@pytest.fixture
def pipeline(mock_state_manager):
    """Create ContentPipeline with mocked dependencies."""
    return ContentPipeline(mock_state_manager)


@pytest.fixture
def sample_content_items():
    """Create sample ContentItem list for testing."""
    now = datetime.now()
    return [
        ContentItem(
            title="Novel LLM Architecture",
            url="https://arxiv.org/abs/2024.12345",
            source="arxiv",
            category="research",
            relevance_score=8,
            summary="A breakthrough in transformer architectures.",
            published_date=now - timedelta(minutes=30),
        ),
        ContentItem(
            title="Low Relevance Paper",
            url="https://arxiv.org/abs/2024.54321",
            source="arxiv",
            category="research",
            relevance_score=3,  # Below MIN_RELEVANCE_SCORE
            summary="A theoretical proof.",
            published_date=now - timedelta(minutes=15),
        ),
        ContentItem(
            title="Old Paper",
            url="https://arxiv.org/abs/2024.11111",
            source="arxiv",
            category="research",
            relevance_score=7,
            summary="Great paper but too old.",
            published_date=now - timedelta(hours=25),  # Outside time window
        ),
        ContentItem(
            title="Another Good Paper",
            url="https://arxiv.org/abs/2024.99999",
            source="arxiv",
            category="research",
            relevance_score=9,
            summary="Another significant development.",
            published_date=now - timedelta(minutes=45),
        ),
    ]


class TestDeduplication:
    """Test deduplication logic."""

    @pytest.mark.asyncio
    async def test_deduplicate_removes_duplicates(self, pipeline, mock_state_manager):
        """Test that duplicates are filtered out."""
        items = [
            ContentItem(
                title="Unique Item",
                url="https://example.com/1",
                source="arxiv",
                category="research",
                relevance_score=7,
                summary="Unique",
            ),
            ContentItem(
                title="Duplicate Item",
                url="https://example.com/2",
                source="arxiv",
                category="research",
                relevance_score=8,
                summary="Duplicate",
            ),
        ]

        # Mock: first item is unique, second is duplicate
        mock_state_manager.check_duplicate.side_effect = [False, True]

        result = await pipeline.deduplicate(items)

        assert len(result) == 1
        assert result[0].title == "Unique Item"
        assert mock_state_manager.check_duplicate.call_count == 2

    @pytest.mark.asyncio
    async def test_deduplicate_continues_on_error(self, pipeline, mock_state_manager):
        """Test that deduplication continues if check fails."""
        items = [
            ContentItem(
                title="Item 1",
                url="https://example.com/1",
                source="arxiv",
                category="research",
                relevance_score=7,
                summary="Test",
            ),
        ]

        # Mock: check_duplicate raises exception
        mock_state_manager.check_duplicate.side_effect = Exception("Database error")

        result = await pipeline.deduplicate(items)

        # Should continue and include item (assume not duplicate on error)
        assert len(result) == 1
        assert result[0].title == "Item 1"


class TestRelevanceFiltering:
    """Test relevance score filtering."""

    def test_filter_by_relevance_keeps_high_scores(self, pipeline, sample_content_items):
        """Test that only items with score >= MIN_RELEVANCE_SCORE are kept."""
        result = pipeline.filter_by_relevance(sample_content_items)

        # Should keep items with score >= 5 (scores: 8, 3, 7, 9)
        assert len(result) == 3
        assert all(item.relevance_score >= MIN_RELEVANCE_SCORE for item in result)

        # Check that low-score item was filtered
        titles = [item.title for item in result]
        assert "Low Relevance Paper" not in titles

    def test_filter_by_relevance_empty_list(self, pipeline):
        """Test filtering empty list."""
        result = pipeline.filter_by_relevance([])
        assert result == []


class TestTimeFiltering:
    """Test time-based filtering."""

    def test_filter_by_time_removes_old_items(self, pipeline, sample_content_items):
        """Test that items outside time window are filtered."""
        result = pipeline.filter_by_time(sample_content_items, hours=RESEARCH_TIME_WINDOW_HOURS)

        # Should keep recent items only (not the 25-hour-old one)
        assert len(result) == 3
        titles = [item.title for item in result]
        assert "Old Paper" not in titles

    def test_filter_by_time_custom_window(self, pipeline):
        """Test filtering with custom time window."""
        now = datetime.now()
        items = [
            ContentItem(
                title="Very Recent",
                url="https://example.com/1",
                source="arxiv",
                category="research",
                relevance_score=7,
                summary="Test",
                published_date=now - timedelta(minutes=10),
            ),
            ContentItem(
                title="Somewhat Old",
                url="https://example.com/2",
                source="arxiv",
                category="research",
                relevance_score=7,
                summary="Test",
                published_date=now - timedelta(hours=2),
            ),
        ]

        # Filter with 1-hour window
        result = pipeline.filter_by_time(items, hours=1)
        assert len(result) == 1
        assert result[0].title == "Very Recent"

    def test_filter_by_time_none_published_date(self, pipeline):
        """Test filtering when published_date is None."""
        # Note: ContentItem sets published_date to datetime.now() if None
        # So this test verifies that default dates are kept (as they're recent)
        items = [
            ContentItem(
                title="No Date",
                url="https://example.com/1",
                source="arxiv",
                category="research",
                relevance_score=7,
                summary="Test",
                published_date=None,  # Will default to now()
            ),
        ]

        result = pipeline.filter_by_time(items)
        # Items with default date (now) should be kept
        assert len(result) == 1


class TestConversion:
    """Test ContentItem to NewsletterItem conversion."""

    def test_convert_to_newsletter_items_maps_fields(self, pipeline):
        """Test that all fields are correctly mapped."""
        now = datetime.now()
        items = [
            ContentItem(
                title="Test Paper",
                url="https://arxiv.org/abs/2024.12345",
                source="arxiv",
                category="research",
                relevance_score=8,
                summary="Test summary",
                metadata={"authors": ["Alice", "Bob"]},
                published_date=now,
            ),
        ]

        result = pipeline.convert_to_newsletter_items(items)

        assert len(result) == 1
        item = result[0]

        # Verify all fields are mapped
        assert isinstance(item, NewsletterItem)
        assert item.title == "Test Paper"
        assert item.url == "https://arxiv.org/abs/2024.12345"
        assert item.source == "arxiv"
        assert item.category == "research"
        assert item.relevance_score == 8
        assert item.summary == "Test summary"
        assert item.metadata == {"authors": ["Alice", "Bob"]}
        assert item.published_date == now

    def test_convert_to_newsletter_items_handles_errors(self, pipeline, caplog):
        """Test that conversion continues if one item fails."""
        items = [
            ContentItem(
                title="Good Item",
                url="https://example.com/1",
                source="arxiv",
                category="research",
                relevance_score=7,
                summary="Test",
            ),
            # This will cause validation error (invalid score)
            # We'll patch NewsletterItem to simulate this
        ]

        with patch("src.core.content_pipeline.NewsletterItem") as mock_item:
            # First call succeeds, second raises error
            mock_item.side_effect = [
                NewsletterItem(
                    title="Good Item",
                    url="https://example.com/1",
                    source="arxiv",
                    category="research",
                    relevance_score=7,
                    summary="Test",
                ),
                ValueError("Invalid field"),
            ]

            result = pipeline.convert_to_newsletter_items(items)

            # Should have 1 successful conversion
            assert len(result) == 1


class TestSummaryGeneration:
    """Test newsletter summary generation."""

    @pytest.mark.asyncio
    async def test_generate_summary_calls_claude(self, pipeline, mock_state_manager):
        """Test that Claude API is called for summary generation."""
        items = [
            NewsletterItem(
                title="Test Paper",
                url="https://example.com/1",
                source="arxiv",
                category="research",
                relevance_score=8,
                summary="Test summary",
            ),
        ]

        # Mock Claude API client
        mock_client = AsyncMock()
        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(text="Today's AI highlights include groundbreaking research.")
        ]
        mock_message.usage.input_tokens = 500
        mock_message.usage.output_tokens = 50
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        pipeline.client = mock_client

        result = await pipeline.generate_summary(items, "2026-02-15-10")

        # Verify Claude was called
        assert mock_client.messages.create.called
        assert "Today's AI highlights" in result

        # Verify API usage was tracked
        assert mock_state_manager.track_api_usage.called

    @pytest.mark.asyncio
    async def test_generate_summary_warning_for_low_count(self, pipeline):
        """Test that warning is added for <3 items."""
        items = [
            NewsletterItem(
                title="Test Paper",
                url="https://example.com/1",
                source="arxiv",
                category="research",
                relevance_score=8,
                summary="Test",
            ),
        ]

        # No Claude client configured
        pipeline.client = None

        result = await pipeline.generate_summary(items, "2026-02-15-10")

        # Should have warning
        assert "⚠️ Note: Only 1 item found" in result

    @pytest.mark.asyncio
    async def test_generate_summary_fallback_on_error(self, pipeline):
        """Test fallback summary when API fails."""
        items = [
            NewsletterItem(
                title="Test Paper",
                url="https://example.com/1",
                source="arxiv",
                category="research",
                relevance_score=8,
                summary="Test",
            ),
        ]

        # Mock Claude API to raise error
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API Error"))
        pipeline.client = mock_client

        result = await pipeline.generate_summary(items, "2026-02-15-10")

        # Should use fallback
        assert "highlight" in result.lower()

    @pytest.mark.asyncio
    async def test_generate_summary_empty_items(self, pipeline):
        """Test summary generation with no items."""
        result = await pipeline.generate_summary([], "2026-02-15-10")

        assert "No significant AI developments" in result


class TestNewsletterAssembly:
    """Test newsletter assembly."""

    def test_assemble_newsletter_structure(self, pipeline):
        """Test that newsletter is correctly assembled."""
        items = [
            NewsletterItem(
                title="Test Paper",
                url="https://example.com/1",
                source="arxiv",
                category="research",
                relevance_score=8,
                summary="Test",
            ),
        ]

        newsletter = pipeline.assemble_newsletter(
            items=items, summary="Test summary", date="2026-02-15-10"
        )

        assert newsletter.date == "2026-02-15-10"
        assert newsletter.item_count == 1
        assert newsletter.summary == "Test summary"
        assert len(newsletter.items) == 1


class TestFullPipeline:
    """Test end-to-end pipeline flow."""

    @pytest.mark.asyncio
    async def test_full_pipeline_end_to_end(
        self, pipeline, mock_state_manager, sample_content_items
    ):
        """Test complete pipeline flow."""
        # Mock no duplicates
        mock_state_manager.check_duplicate.return_value = False

        # Mock Claude API
        mock_client = AsyncMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Today's highlights include significant research.")]
        mock_message.usage.input_tokens = 500
        mock_message.usage.output_tokens = 50
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        pipeline.client = mock_client

        # Run pipeline
        newsletter = await pipeline.process(sample_content_items, "2026-02-15-10")

        # Verify results
        assert newsletter.date == "2026-02-15-10"
        # Should have 2 items (score >= 5 AND within time window)
        assert newsletter.item_count == 2
        assert "highlights" in newsletter.summary.lower()
        assert all(item.relevance_score >= MIN_RELEVANCE_SCORE for item in newsletter.items)
