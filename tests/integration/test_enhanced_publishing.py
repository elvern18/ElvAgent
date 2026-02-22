"""
Integration tests for enhanced content publishing.

Tests the full flow: NewsletterItems → ContentEnhancer → TelegramPublisher
"""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from src.models.newsletter import NewsletterItem
from src.publishing.content_enhancer import ContentEnhancer
from src.publishing.telegram_publisher import TelegramPublisher


@pytest.fixture
def mock_anthropic_api(monkeypatch):
    """Mock Anthropic API calls for all enhancers."""

    # Mock HeadlineWriter
    async def mock_generate_headline(self, item, timeout=30):
        return (f"🔬 {item.title[:40].lower()}", 0.0025)

    # Mock TakeawayGenerator
    async def mock_generate_takeaway(self, item, headline, timeout=30):
        return ("interesting for AI development. worth watching.", 0.0012)

    # Mock SocialFormatter
    async def mock_format_category(self, category, title, items, date, timeout=30):
        formatted = f"**{title}**\n\n"
        for idx, item in enumerate(items, 1):
            formatted += f"{idx}. **{item.viral_headline}**\n"
            formatted += f"   {item.takeaway}\n"
            formatted += f"   🔗 [Read more]({item.url})\n\n"
        formatted += "━━━━━━━━━━━━━━━━"
        return (formatted, 0.0008)

    monkeypatch.setattr(
        "src.publishing.enhancers.headline_writer.HeadlineWriter.generate_headline",
        mock_generate_headline,
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.takeaway_generator.TakeawayGenerator.generate_takeaway",
        mock_generate_takeaway,
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.social_formatter.SocialFormatter.format_category",
        mock_format_category,
    )


@pytest.fixture
def mock_telegram_bot(monkeypatch):
    """Mock Telegram Bot API."""

    # Create mock bot that doesn't validate markdown
    mock_bot_instance = AsyncMock()

    # Mock send_message to return a message object
    # Bypass all validation - just accept any input
    async def mock_send_message(*args, **kwargs):
        mock_message = Mock()
        mock_message.message_id = 12345
        return mock_message

    mock_bot_instance.send_message = mock_send_message

    # Mock Bot class
    class MockBot:
        def __init__(self, token):
            pass

        async def send_message(self, *args, **kwargs):
            return await mock_send_message(*args, **kwargs)

    # Patch where Bot is imported in telegram_publisher
    monkeypatch.setattr("src.publishing.telegram_publisher.Bot", MockBot)

    # Patch credentials so validate_credentials() returns True
    monkeypatch.setattr(
        "src.publishing.telegram_publisher.settings",
        MagicMock(telegram_bot_token="fake-token", telegram_chat_id="-100123456"),
    )

    return mock_bot_instance


@pytest.mark.asyncio
@pytest.mark.integration
async def test_end_to_end_enhancement_and_publish(
    sample_newsletter_items, mock_anthropic_api, mock_telegram_bot
):
    """Test full flow: NewsletterItems → Enhanced → Published to Telegram."""

    # Step 1: Create ContentEnhancer
    enhancer = ContentEnhancer()

    # Step 2: Enhance newsletter items
    category_messages, metrics = await enhancer.enhance_newsletter(
        items=sample_newsletter_items, date="2026-02-17"
    )

    # Verify enhancement results
    assert len(category_messages) > 0
    assert metrics.total_items == len(sample_newsletter_items)
    assert metrics.ai_enhanced > 0
    assert metrics.total_cost > 0

    # Verify category messages structure
    for msg in category_messages:
        assert msg.category
        assert msg.emoji
        assert msg.title
        assert len(msg.items) > 0
        assert msg.formatted_text
        assert msg.item_count == len(msg.items)

    # Step 3: Create TelegramPublisher
    publisher = TelegramPublisher()

    # Step 4: Publish enhanced messages
    result = await publisher.publish_enhanced(category_messages)

    # Verify publish result
    assert result.success
    assert result.platform == "telegram"
    assert "message(s)" in result.message.lower() or "message" in result.message.lower()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_enhancement_with_failures_still_publishes(
    sample_newsletter_items, mock_telegram_bot, monkeypatch
):
    """Test that partial AI failures still result in successful publishing."""

    # Mock: some AI calls fail
    call_count = {"headline": 0, "takeaway": 0}

    async def mock_generate_headline_partial(self, item, timeout=30):
        call_count["headline"] += 1
        if call_count["headline"] % 2 == 0:  # Every 2nd call fails
            raise Exception("API error")
        return (f"🔬 {item.title[:40].lower()}", 0.0025)

    async def mock_generate_takeaway(self, item, headline, timeout=30):
        call_count["takeaway"] += 1
        return ("interesting approach. worth watching.", 0.0012)

    async def mock_format_category(self, category, title, items, date, timeout=30):
        return (f"**{title}**\n\nFormatted content", 0.0008)

    monkeypatch.setattr(
        "src.publishing.enhancers.headline_writer.HeadlineWriter.generate_headline",
        mock_generate_headline_partial,
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.takeaway_generator.TakeawayGenerator.generate_takeaway",
        mock_generate_takeaway,
    )
    monkeypatch.setattr(
        "src.publishing.enhancers.social_formatter.SocialFormatter.format_category",
        mock_format_category,
    )

    # Step 1: Enhance (some will fail)
    enhancer = ContentEnhancer()
    category_messages, metrics = await enhancer.enhance_newsletter(
        items=sample_newsletter_items, date="2026-02-17"
    )

    # Verify partial success (some items may use templates)
    assert metrics.total_items == len(sample_newsletter_items)
    assert metrics.ai_enhanced + metrics.template_fallback == metrics.total_items
    # Note: With retry logic, failures may succeed on retry, so we just verify
    # that all items were processed one way or another

    # Step 2: Publish (should still succeed)
    publisher = TelegramPublisher()
    result = await publisher.publish_enhanced(category_messages)

    # Verify publishing succeeded despite enhancement failures
    assert result.success


@pytest.mark.asyncio
@pytest.mark.integration
async def test_enhancement_cost_tracking(
    sample_newsletter_items, mock_anthropic_api, mock_telegram_bot
):
    """Test that enhancement costs are accurately tracked."""

    # Enhance
    enhancer = ContentEnhancer()
    category_messages, metrics = await enhancer.enhance_newsletter(
        items=sample_newsletter_items, date="2026-02-17"
    )

    # Verify cost tracking
    assert metrics.total_cost > 0
    assert metrics.total_time_seconds > 0
    assert metrics.avg_time_per_item > 0

    # Cost should be reasonable (mocked costs are ~$0.0025 + $0.0012 per item)
    # Plus category formatting (~$0.0008 per category)
    expected_min_cost = metrics.ai_enhanced * 0.003  # Conservative estimate
    expected_max_cost = metrics.total_items * 0.01  # Upper bound
    assert expected_min_cost <= metrics.total_cost <= expected_max_cost


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_categories_published_separately(mock_anthropic_api, mock_telegram_bot):
    """Test that items from multiple categories are grouped and published."""

    # Create items from different categories
    items = [
        NewsletterItem(
            title="Research Item 1",
            url="https://example.com/1",
            summary="Research summary",
            category="research",
            source="arxiv",
            relevance_score=9,
        ),
        NewsletterItem(
            title="Research Item 2",
            url="https://example.com/2",
            summary="Another research summary",
            category="research",
            source="arxiv",
            relevance_score=8,
        ),
        NewsletterItem(
            title="Funding Item 1",
            url="https://example.com/3",
            summary="Funding summary",
            category="funding",
            source="techcrunch",
            relevance_score=7,
        ),
        NewsletterItem(
            title="Product Item 1",
            url="https://example.com/4",
            summary="Product summary",
            category="product",
            source="news",
            relevance_score=10,
        ),
    ]

    # Enhance
    enhancer = ContentEnhancer()
    category_messages, metrics = await enhancer.enhance_newsletter(items=items, date="2026-02-17")

    # Verify multiple categories
    assert len(category_messages) == 3  # research, funding, product
    categories = {msg.category for msg in category_messages}
    assert "research" in categories
    assert "funding" in categories
    assert "product" in categories

    # Verify each category has correct items
    research_msg = next(msg for msg in category_messages if msg.category == "research")
    assert research_msg.item_count == 2

    funding_msg = next(msg for msg in category_messages if msg.category == "funding")
    assert funding_msg.item_count == 1

    product_msg = next(msg for msg in category_messages if msg.category == "product")
    assert product_msg.item_count == 1

    # Publish
    publisher = TelegramPublisher()
    result = await publisher.publish_enhanced(category_messages)

    # Verify all categories published
    assert result.success


@pytest.mark.asyncio
@pytest.mark.integration
async def test_empty_items_handled_gracefully(mock_anthropic_api, mock_telegram_bot):
    """Test that empty item list is handled gracefully."""

    # Enhance with empty list
    enhancer = ContentEnhancer()
    category_messages, metrics = await enhancer.enhance_newsletter(items=[], date="2026-02-17")

    # Verify empty results
    assert len(category_messages) == 0
    assert metrics.total_items == 0
    assert metrics.total_cost == 0.0

    # Publishing empty list should work
    publisher = TelegramPublisher()

    # Note: Telegram might return an error for empty content,
    # but the formatter should still handle it gracefully
    formatted = publisher.formatter.format_enhanced(category_messages)
    assert isinstance(formatted, list)
