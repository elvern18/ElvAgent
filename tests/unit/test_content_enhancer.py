"""
Unit tests for ContentEnhancer orchestrator.

Tests sequential enhancement, retry logic, template fallbacks,
category grouping, and metrics tracking.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from src.publishing.content_enhancer import ContentEnhancer
from src.models.newsletter import NewsletterItem
from src.models.enhanced_newsletter import (
    EnhancedNewsletterItem,
    CategoryMessage,
    EnhancementMetrics
)


@pytest.fixture
def content_enhancer():
    """Create ContentEnhancer instance."""
    return ContentEnhancer()


@pytest.fixture
def mock_enhancers(monkeypatch):
    """Mock all enhancement components."""

    # Mock HeadlineWriter
    async def mock_generate_headline(self, item, timeout=30):
        return (f"🔬 Mocked: {item.title[:30]}", 0.0025)

    # Mock TakeawayGenerator
    async def mock_generate_takeaway(self, item, headline, timeout=30):
        return ("💡 Why it matters: Mocked takeaway", 0.0012)

    # Mock EngagementEnricher
    def mock_enrich_metrics(self, item):
        return {"read_time": "☕ 3-min read"}

    # Mock SocialFormatter
    async def mock_format_category(self, category, title, items, date, timeout=30):
        text = f"**{title}**\n\nMocked formatted content"
        return (text, 0.0008)

    def mock_format_category_simple(self, category, title, items):
        return f"**{title}**\n\nSimple formatted content"

    monkeypatch.setattr(
        "src.publishing.enhancers.headline_writer.HeadlineWriter.generate_headline",
        mock_generate_headline
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.takeaway_generator.TakeawayGenerator.generate_takeaway",
        mock_generate_takeaway
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.engagement_enricher.EngagementEnricher.enrich_metrics",
        mock_enrich_metrics
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.social_formatter.SocialFormatter.format_category",
        mock_format_category
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.social_formatter.SocialFormatter.format_category_simple",
        mock_format_category_simple
    )


@pytest.mark.asyncio
async def test_enhance_newsletter_all_ai_success(
    content_enhancer,
    sample_newsletter_items,
    mock_enhancers
):
    """Test successful enhancement of all items with AI."""
    # Run enhancement
    category_messages, metrics = await content_enhancer.enhance_newsletter(
        items=sample_newsletter_items,
        date="2026-02-17"
    )

    # Verify metrics
    assert metrics.total_items == 3
    assert metrics.ai_enhanced == 3
    assert metrics.template_fallback == 0
    assert metrics.success_rate == 100.0
    assert metrics.total_cost > 0
    assert metrics.total_time_seconds > 0

    # Verify category messages created
    assert len(category_messages) > 0

    # Verify each category message has required fields
    for msg in category_messages:
        assert msg.category
        assert msg.emoji
        assert msg.title
        assert len(msg.items) > 0
        assert msg.formatted_text
        assert msg.item_count == len(msg.items)


@pytest.mark.asyncio
async def test_enhance_newsletter_partial_failure(
    content_enhancer,
    sample_newsletter_items,
    monkeypatch
):
    """Test enhancement with some AI failures falling back to templates."""

    # Mock: first item succeeds, second fails all retries, third succeeds
    call_count = {"count": 0}

    async def mock_generate_headline_partial(self, item, timeout=30):
        call_count["count"] += 1
        # Fail attempts 2, 3, 4 (second item with 3 retries)
        if 2 <= call_count["count"] <= 4:
            raise Exception("API error")
        return (f"🔬 Mocked: {item.title[:30]}", 0.0025)

    async def mock_generate_takeaway(self, item, headline, timeout=30):
        return ("💡 Why it matters: Mocked takeaway", 0.0012)

    def mock_enrich_metrics(self, item):
        return {"read_time": "☕ 3-min read"}

    async def mock_format_category(self, category, title, items, date, timeout=30):
        return (f"**{title}**", 0.0008)

    monkeypatch.setattr(
        "src.publishing.enhancers.headline_writer.HeadlineWriter.generate_headline",
        mock_generate_headline_partial
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.takeaway_generator.TakeawayGenerator.generate_takeaway",
        mock_generate_takeaway
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.engagement_enricher.EngagementEnricher.enrich_metrics",
        mock_enrich_metrics
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.social_formatter.SocialFormatter.format_category",
        mock_format_category
    )

    # Run enhancement
    category_messages, metrics = await content_enhancer.enhance_newsletter(
        items=sample_newsletter_items,
        date="2026-02-17"
    )

    # Verify partial success
    assert metrics.total_items == 3
    assert metrics.ai_enhanced == 2  # First and third succeeded
    assert metrics.template_fallback == 1  # Second failed
    assert 60 <= metrics.success_rate <= 70  # ~66.7%
    assert metrics.total_cost > 0  # Only AI-enhanced items cost money


@pytest.mark.asyncio
async def test_enhance_newsletter_all_template(
    content_enhancer,
    sample_newsletter_items,
    monkeypatch
):
    """Test enhancement when all AI calls fail (all templates)."""

    # Mock: all AI calls fail
    async def mock_generate_headline_fail(self, item, timeout=30):
        raise Exception("API error")

    async def mock_generate_takeaway_fail(self, item, headline, timeout=30):
        raise Exception("API error")

    def mock_enrich_metrics(self, item):
        return {"read_time": "☕ 3-min read"}

    async def mock_format_category(self, category, title, items, date, timeout=30):
        return (f"**{title}**", 0.0008)

    monkeypatch.setattr(
        "src.publishing.enhancers.headline_writer.HeadlineWriter.generate_headline",
        mock_generate_headline_fail
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.takeaway_generator.TakeawayGenerator.generate_takeaway",
        mock_generate_takeaway_fail
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.engagement_enricher.EngagementEnricher.enrich_metrics",
        mock_enrich_metrics
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.social_formatter.SocialFormatter.format_category",
        mock_format_category
    )

    # Run enhancement
    category_messages, metrics = await content_enhancer.enhance_newsletter(
        items=sample_newsletter_items,
        date="2026-02-17"
    )

    # Verify all templates used
    assert metrics.total_items == 3
    assert metrics.ai_enhanced == 0
    assert metrics.template_fallback == 3
    assert metrics.success_rate == 0.0

    # Still produces output
    assert len(category_messages) > 0


@pytest.mark.asyncio
async def test_enhance_single_item_retry_logic(
    content_enhancer,
    sample_newsletter_items,
    monkeypatch
):
    """Test retry logic for single item enhancement."""

    # Track retry attempts
    attempts = {"headline": 0, "takeaway": 0}

    async def mock_generate_headline_retry(self, item, timeout=30):
        attempts["headline"] += 1
        if attempts["headline"] < 3:
            raise Exception("Temporary error")
        return (f"🔬 Success on attempt 3", 0.0025)

    async def mock_generate_takeaway(self, item, headline, timeout=30):
        attempts["takeaway"] += 1
        return ("💡 Why it matters: Success", 0.0012)

    def mock_enrich_metrics(self, item):
        return {"read_time": "☕ 3-min read"}

    async def mock_format_category(self, category, title, items, date, timeout=30):
        return (f"**{title}**", 0.0008)

    monkeypatch.setattr(
        "src.publishing.enhancers.headline_writer.HeadlineWriter.generate_headline",
        mock_generate_headline_retry
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.takeaway_generator.TakeawayGenerator.generate_takeaway",
        mock_generate_takeaway
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.engagement_enricher.EngagementEnricher.enrich_metrics",
        mock_enrich_metrics
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.social_formatter.SocialFormatter.format_category",
        mock_format_category
    )

    # Run enhancement (single item)
    category_messages, metrics = await content_enhancer.enhance_newsletter(
        items=[sample_newsletter_items[0]],
        date="2026-02-17"
    )

    # Verify retry happened and succeeded
    assert attempts["headline"] == 3  # Retried 3 times before success
    assert metrics.ai_enhanced == 1
    assert metrics.template_fallback == 0


def test_group_by_category(content_enhancer, sample_enhanced_items):
    """Test category grouping logic."""
    # Create more items in same categories to test limit
    from src.models.newsletter import NewsletterItem
    from src.models.enhanced_newsletter import EnhancedNewsletterItem

    extra_items = []
    for i in range(6):
        item = NewsletterItem(
            title=f"Research Item {i}",
            url=f"https://example.com/{i}",
            summary="Summary",
            category="research",
            source="test",
            relevance_score=10 - i  # Descending scores
        )
        enhanced = EnhancedNewsletterItem(
            original_item=item,
            viral_headline=f"Headline {i}",
            takeaway="Takeaway",
            engagement_metrics={},
            enhancement_method="ai",
            enhancement_cost=0.0
        )
        extra_items.append(enhanced)

    # Group with max 5 per category
    all_items = sample_enhanced_items + extra_items
    grouped = content_enhancer._group_by_category(all_items, max_per_category=5)

    # Verify grouping
    assert "research" in grouped
    assert len(grouped["research"]) == 5  # Max limit applied

    # Verify sorted by relevance_score (descending)
    research_items = grouped["research"]
    scores = [item.relevance_score for item in research_items]
    assert scores == sorted(scores, reverse=True)


def test_group_by_category_limit_five(content_enhancer):
    """Test that max 5 items per category is enforced."""
    from src.models.newsletter import NewsletterItem
    from src.models.enhanced_newsletter import EnhancedNewsletterItem

    # Create 10 items in "research" category
    items = []
    for i in range(10):
        item = NewsletterItem(
            title=f"Item {i}",
            url=f"https://example.com/{i}",
            summary="Summary",
            category="research",
            source="test",
            relevance_score=10 - i
        )
        enhanced = EnhancedNewsletterItem(
            original_item=item,
            viral_headline=f"Headline {i}",
            takeaway="Takeaway",
            engagement_metrics={},
            enhancement_method="ai",
            enhancement_cost=0.0
        )
        items.append(enhanced)

    # Group
    grouped = content_enhancer._group_by_category(items, max_per_category=5)

    # Verify only top 5 kept
    assert len(grouped["research"]) == 5

    # Verify top 5 by score (highest scores)
    kept_scores = [item.relevance_score for item in grouped["research"]]
    assert kept_scores == [10, 9, 8, 7, 6]


@pytest.mark.asyncio
async def test_format_category_ai_success(
    content_enhancer,
    sample_enhanced_items,
    monkeypatch
):
    """Test category formatting with AI."""

    # Mock SocialFormatter
    async def mock_format_category(category, title, items, date, timeout=30):
        return ("**FORMATTED TEXT**\nWith AI", 0.0015)

    monkeypatch.setattr(
        "src.publishing.enhancers.social_formatter.SocialFormatter.format_category",
        mock_format_category
    )

    # Format category
    metrics = EnhancementMetrics()
    msg = await content_enhancer._format_category_message(
        category="research",
        items=[sample_enhanced_items[0]],
        date="2026-02-17",
        metrics=metrics
    )

    # Verify
    assert msg.category == "research"
    assert msg.emoji == "🔬"
    assert "FORMATTED TEXT" in msg.formatted_text
    assert metrics.total_cost == 0.0015


@pytest.mark.asyncio
async def test_format_category_fallback(
    content_enhancer,
    sample_enhanced_items,
    monkeypatch
):
    """Test category formatting with simple fallback."""

    # Mock SocialFormatter to fail
    async def mock_format_category_fail(self, category, title, items, date, timeout=30):
        raise Exception("API error")

    def mock_format_category_simple(self, category, title, items):
        return "**SIMPLE FORMATTED TEXT**"

    monkeypatch.setattr(
        "src.publishing.enhancers.social_formatter.SocialFormatter.format_category",
        mock_format_category_fail
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.social_formatter.SocialFormatter.format_category_simple",
        mock_format_category_simple
    )

    # Format category
    metrics = EnhancementMetrics()
    msg = await content_enhancer._format_category_message(
        category="research",
        items=[sample_enhanced_items[0]],
        date="2026-02-17",
        metrics=metrics
    )

    # Verify fallback used
    assert "SIMPLE FORMATTED TEXT" in msg.formatted_text
    assert metrics.total_cost == 0.0  # No cost for fallback


def test_enhancement_metrics_tracking():
    """Test EnhancementMetrics calculations."""
    metrics = EnhancementMetrics(
        total_items=10,
        ai_enhanced=7,
        template_fallback=3,
        total_cost=0.15,
        total_time_seconds=45.5
    )

    # Test success rate
    assert metrics.success_rate == 70.0

    # Test avg time per item
    assert metrics.avg_time_per_item == 4.55

    # Test to_dict
    data = metrics.to_dict()
    assert data["total_items"] == 10
    assert data["ai_enhanced"] == 7
    assert data["template_fallback"] == 3
    assert data["success_rate"] == 70.0
    assert data["avg_time_per_item"] == 4.55


@pytest.mark.asyncio
async def test_empty_newsletter(content_enhancer, mock_enhancers):
    """Test handling of empty newsletter."""

    # Run with empty list
    category_messages, metrics = await content_enhancer.enhance_newsletter(
        items=[],
        date="2026-02-17"
    )

    # Verify
    assert metrics.total_items == 0
    assert metrics.ai_enhanced == 0
    assert metrics.template_fallback == 0
    assert metrics.success_rate == 0.0
    assert len(category_messages) == 0
