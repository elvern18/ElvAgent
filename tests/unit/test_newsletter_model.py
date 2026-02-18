"""
Unit tests for Newsletter data models.
"""

import pytest
from pydantic import ValidationError

from src.models.newsletter import Newsletter, NewsletterItem


@pytest.mark.unit
class TestNewsletterItem:
    """Tests for NewsletterItem model."""

    def test_valid_item_creation(self):
        """Test creating a valid newsletter item."""
        item = NewsletterItem(
            title="Novel LLM Architecture",
            url="https://arxiv.org/abs/2024.12345",
            summary="Researchers propose a new transformer architecture...",
            category="research",
            source="arxiv",
            relevance_score=9,
        )

        assert item.title == "Novel LLM Architecture"
        assert item.url == "https://arxiv.org/abs/2024.12345"
        assert item.category == "research"
        assert item.source == "arxiv"
        assert item.relevance_score == 9
        assert item.metadata == {}

    def test_item_with_metadata(self):
        """Test item with additional metadata."""
        item = NewsletterItem(
            title="GPT-5 Release",
            url="https://openai.com/gpt5",
            summary="Major update",
            category="product",
            source="news",
            relevance_score=10,
            metadata={"authors": ["OpenAI"], "citations": 100},
        )

        assert item.metadata == {"authors": ["OpenAI"], "citations": 100}

    def test_relevance_score_validation(self):
        """Test that relevance score must be 1-10."""
        # Valid scores
        item = NewsletterItem(
            title="Test",
            url="https://example.com",
            summary="Test",
            category="research",
            source="test",
            relevance_score=1,
        )
        assert item.relevance_score == 1

        item.relevance_score = 10
        assert item.relevance_score == 10

        # Invalid scores
        with pytest.raises(ValidationError):
            NewsletterItem(
                title="Test",
                url="https://example.com",
                summary="Test",
                category="research",
                source="test",
                relevance_score=0,  # Too low
            )

        with pytest.raises(ValidationError):
            NewsletterItem(
                title="Test",
                url="https://example.com",
                summary="Test",
                category="research",
                source="test",
                relevance_score=11,  # Too high
            )

    def test_category_normalization(self):
        """Test that category is normalized to lowercase."""
        item = NewsletterItem(
            title="Test",
            url="https://example.com",
            summary="Test",
            category="RESEARCH",  # Uppercase
            source="arxiv",
            relevance_score=5,
        )

        assert item.category == "research"

    def test_source_normalization(self):
        """Test that source is normalized to lowercase."""
        item = NewsletterItem(
            title="Test",
            url="https://example.com",
            summary="Test",
            category="research",
            source="ArXiv",  # Mixed case
            relevance_score=5,
        )

        assert item.source == "arxiv"


@pytest.mark.unit
class TestNewsletter:
    """Tests for Newsletter model."""

    def test_valid_newsletter_creation(self):
        """Test creating a valid newsletter."""
        items = [
            NewsletterItem(
                title="Item 1",
                url="https://example.com/1",
                summary="First item",
                category="research",
                source="arxiv",
                relevance_score=9,
            ),
            NewsletterItem(
                title="Item 2",
                url="https://example.com/2",
                summary="Second item",
                category="product",
                source="news",
                relevance_score=8,
            ),
        ]

        newsletter = Newsletter(
            date="2026-02-15-10", items=items, summary="Today's top AI updates", item_count=2
        )

        assert newsletter.date == "2026-02-15-10"
        assert len(newsletter.items) == 2
        assert newsletter.summary == "Today's top AI updates"
        assert newsletter.item_count == 2

    def test_item_count_validation(self):
        """Test that item_count must match items length."""
        items = [
            NewsletterItem(
                title="Item 1",
                url="https://example.com/1",
                summary="First item",
                category="research",
                source="arxiv",
                relevance_score=9,
            )
        ]

        # Valid - item_count matches
        newsletter = Newsletter(date="2026-02-15-10", items=items, item_count=1)
        assert newsletter.item_count == 1

        # Invalid - item_count doesn't match
        with pytest.raises(ValidationError) as exc_info:
            Newsletter(
                date="2026-02-15-10",
                items=items,
                item_count=2,  # Wrong count
            )

        assert "item_count 2 doesn't match items length 1" in str(exc_info.value)

    def test_date_format_validation(self):
        """Test date format validation."""
        items = [
            NewsletterItem(
                title="Test",
                url="https://example.com",
                summary="Test",
                category="research",
                source="test",
                relevance_score=5,
            )
        ]

        # Valid formats
        valid_dates = ["2026-02-15-10", "2026-01-01-00", "2026-12-31-23"]
        for date in valid_dates:
            newsletter = Newsletter(date=date, items=items, item_count=1)
            assert newsletter.date == date

        # Invalid formats
        invalid_dates = [
            "2026-02-15",  # Missing hour
            "2026-13-01-10",  # Invalid month
            "2026-02-32-10",  # Invalid day
            "2026-02-15-24",  # Invalid hour
            "not-a-date",  # Invalid format
        ]

        for date in invalid_dates:
            with pytest.raises(ValidationError):
                Newsletter(date=date, items=items, item_count=1)

    def test_empty_newsletter(self):
        """Test newsletter with no items."""
        newsletter = Newsletter(date="2026-02-15-10", items=[], item_count=0)

        assert len(newsletter.items) == 0
        assert newsletter.item_count == 0

    def test_to_dict_conversion(self):
        """Test converting newsletter to dictionary."""
        items = [
            NewsletterItem(
                title="Test Item",
                url="https://example.com",
                summary="Test summary",
                category="research",
                source="test",
                relevance_score=7,
            )
        ]

        newsletter = Newsletter(
            date="2026-02-15-10", items=items, summary="Test newsletter", item_count=1
        )

        data = newsletter.to_dict()

        assert isinstance(data, dict)
        assert data["date"] == "2026-02-15-10"
        assert data["summary"] == "Test newsletter"
        assert data["item_count"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Test Item"

    def test_from_dict_creation(self):
        """Test creating newsletter from dictionary."""
        data = {
            "date": "2026-02-15-10",
            "items": [
                {
                    "title": "Test",
                    "url": "https://example.com",
                    "summary": "Summary",
                    "category": "research",
                    "source": "test",
                    "relevance_score": 8,
                    "published_date": None,
                    "metadata": {},
                }
            ],
            "summary": "Test",
            "item_count": 1,
        }

        newsletter = Newsletter.from_dict(data)

        assert newsletter.date == "2026-02-15-10"
        assert len(newsletter.items) == 1
        assert newsletter.items[0].title == "Test"

    def test_default_summary(self):
        """Test that summary defaults to empty string."""
        newsletter = Newsletter(date="2026-02-15-10", items=[], item_count=0)

        assert newsletter.summary == ""
