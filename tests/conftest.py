"""
Pytest configuration and shared fixtures.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

# Set test environment variables before importing settings
os.environ["DATABASE_PATH"] = ":memory:"  # Use in-memory SQLite for tests
os.environ["LOG_LEVEL"] = "WARNING"  # Reduce noise in tests
os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"  # Mock API key for tests

from src.config.settings import Settings
from src.core.state_manager import StateManager
from src.models.newsletter import Newsletter, NewsletterItem


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_settings(temp_dir):
    """Create test settings with temporary paths."""
    return Settings(
        database_path=temp_dir / "test.db",
        anthropic_api_key="test-key-not-real",
        log_level="WARNING",
    )


@pytest.fixture
async def state_manager(temp_dir):
    """Create a state manager with in-memory database."""
    db_path = temp_dir / "test.db"
    manager = StateManager(db_path=db_path)
    await manager.init_db()
    yield manager
    # Cleanup happens automatically with temp_dir


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for testing without network calls."""
    mock_client = AsyncMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    mock_client.get.return_value = mock_response
    return mock_client


@pytest.fixture
def sample_arxiv_feed():
    """Sample ArXiv RSS feed XML for testing."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>cs.AI updates on arXiv.org</title>
    <item>
      <title>Novel LLM Architecture for Reasoning</title>
      <link>https://arxiv.org/abs/2024.12345</link>
      <description>We present a novel architecture for large language models...</description>
      <author>John Doe, Jane Smith</author>
      <pubDate>Mon, 15 Feb 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Theoretical Bounds on Neural Networks</title>
      <link>https://arxiv.org/abs/2024.12346</link>
      <description>This paper proves theoretical bounds...</description>
      <author>Alice Johnson</author>
      <pubDate>Mon, 15 Feb 2026 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def sample_content_items():
    """Sample ContentItem objects for testing."""
    from datetime import datetime

    from src.research.base import ContentItem

    return [
        ContentItem(
            title="Novel LLM Architecture",
            url="https://arxiv.org/abs/2024.12345",
            source="arxiv",
            category="research",
            relevance_score=9,
            summary="A breakthrough in LLM architecture...",
            metadata={"authors": ["John Doe", "Jane Smith"]},
            published_date=datetime(2026, 2, 15, 10, 0),
        ),
        ContentItem(
            title="New Multimodal Model",
            url="https://huggingface.co/papers/abc123",
            source="huggingface",
            category="research",
            relevance_score=8,
            summary="Combining vision and language...",
            metadata={"downloads": 10000},
            published_date=datetime(2026, 2, 15, 9, 0),
        ),
        ContentItem(
            title="AI Startup Raises $100M",
            url="https://techcrunch.com/funding/xyz",
            source="techcrunch",
            category="funding",
            relevance_score=7,
            summary="Seed funding for AI infrastructure...",
            metadata={"amount": "100M", "investors": ["a16z"]},
            published_date=datetime(2026, 2, 15, 8, 0),
        ),
    ]


@pytest.fixture
def mock_newsletter_data():
    """Sample newsletter data dictionary for testing (backward compatibility)."""
    return {
        "date": "2026-02-15-10",
        "items": [
            {
                "title": "Novel LLM Architecture",
                "url": "https://arxiv.org/abs/2024.12345",
                "summary": "Breakthrough in reasoning...",
                "category": "research",
                "source": "arxiv",
                "relevance_score": 9,
                "published_date": None,
                "metadata": {},
            },
            {
                "title": "AI Startup Raises $100M",
                "url": "https://techcrunch.com/funding/xyz",
                "summary": "Major funding round...",
                "category": "funding",
                "source": "techcrunch",
                "relevance_score": 8,
                "published_date": None,
                "metadata": {},
            },
        ],
        "summary": "Today's AI highlights include a novel LLM architecture and major funding.",
        "item_count": 2,
    }


@pytest.fixture
def sample_newsletter_items():
    """Sample NewsletterItem objects for testing."""
    return [
        NewsletterItem(
            title="Novel LLM Architecture",
            url="https://arxiv.org/abs/2024.12345",
            summary="Researchers propose a new transformer architecture that improves efficiency.",
            category="research",
            source="arxiv",
            relevance_score=9,
        ),
        NewsletterItem(
            title="OpenAI Releases GPT-5",
            url="https://openai.com/gpt5",
            summary="Major update with multimodal capabilities and reasoning.",
            category="product",
            source="news",
            relevance_score=10,
        ),
        NewsletterItem(
            title="Anthropic Raises $500M",
            url="https://techcrunch.com/funding",
            summary="Series C funding led by major investors.",
            category="funding",
            source="techcrunch",
            relevance_score=8,
        ),
    ]


@pytest.fixture
def sample_newsletter(sample_newsletter_items):
    """Sample Newsletter object for testing publishers."""
    return Newsletter(
        date="2026-02-15-10",
        items=sample_newsletter_items,
        summary="Today's top AI updates including breakthrough research and major funding.",
        item_count=3,
    )


@pytest.fixture
def sample_enhanced_items(sample_newsletter_items):
    """Enhanced newsletter items with AI-generated content."""
    from src.models.enhanced_newsletter import EnhancedNewsletterItem

    return [
        EnhancedNewsletterItem(
            original_item=sample_newsletter_items[0],
            viral_headline="🔬 AI Breakthrough: New Transformer Cuts Training Time by 90%",
            takeaway="💡 Why it matters: Makes state-of-the-art models accessible to small research teams",
            engagement_metrics={"read_time": "☕ 5-min read", "authors": "John Doe et al."},
            enhancement_method="ai",
            enhancement_cost=0.0025,
        ),
        EnhancedNewsletterItem(
            original_item=sample_newsletter_items[1],
            viral_headline="🚀 OpenAI's GPT-5: First AI That Truly Reasons Like Humans",
            takeaway="💡 Why it matters: Represents major leap in AI capabilities and practical applications",
            engagement_metrics={"read_time": "☕ 3-min read"},
            enhancement_method="ai",
            enhancement_cost=0.0028,
        ),
        EnhancedNewsletterItem(
            original_item=sample_newsletter_items[2],
            viral_headline="💰 Anthropic Raises $500M to Challenge OpenAI Dominance",
            takeaway="💡 Why it matters: Accelerates competition in foundation models market",
            engagement_metrics={"read_time": "☕ 2-min read", "author": "TechCrunch"},
            enhancement_method="ai",
            enhancement_cost=0.0022,
        ),
    ]


@pytest.fixture
def sample_category_messages(sample_enhanced_items):
    """Sample CategoryMessage objects."""
    from src.models.enhanced_newsletter import CategoryMessage

    # Group by category
    research_items = [item for item in sample_enhanced_items if item.category == "research"]
    product_items = [item for item in sample_enhanced_items if item.category == "product"]
    funding_items = [item for item in sample_enhanced_items if item.category == "funding"]

    messages = []

    if research_items:
        messages.append(
            CategoryMessage(
                category="research",
                emoji="🔬",
                title="🔬 RESEARCH HIGHLIGHTS - 2026-02-15",
                items=research_items,
                formatted_text="**🔬 RESEARCH HIGHLIGHTS**\n\n1. **🔬 AI Breakthrough: New Transformer Cuts Training Time by 90%**\n   💡 Why it matters: Makes state-of-the-art models accessible to small research teams\n   ☕ 5-min read · John Doe et al.\n   🔗 [Read more](https://arxiv.org/abs/2024.12345)\n\n━━━━━━━━━━━━━━━━",
            )
        )

    if product_items:
        messages.append(
            CategoryMessage(
                category="product",
                emoji="🚀",
                title="🚀 NEW LAUNCHES - 2026-02-15",
                items=product_items,
                formatted_text="**🚀 NEW LAUNCHES**\n\n1. **🚀 OpenAI's GPT-5: First AI That Truly Reasons Like Humans**\n   💡 Why it matters: Represents major leap in AI capabilities and practical applications\n   ☕ 3-min read\n   🔗 [Read more](https://openai.com/gpt5)\n\n━━━━━━━━━━━━━━━━",
            )
        )

    if funding_items:
        messages.append(
            CategoryMessage(
                category="funding",
                emoji="💰",
                title="💰 FUNDING ROUNDUP - 2026-02-15",
                items=funding_items,
                formatted_text="**💰 FUNDING ROUNDUP**\n\n1. **💰 Anthropic Raises $500M to Challenge OpenAI Dominance**\n   💡 Why it matters: Accelerates competition in foundation models market\n   ☕ 2-min read · TechCrunch\n   🔗 [Read more](https://techcrunch.com/funding)\n\n━━━━━━━━━━━━━━━━",
            )
        )

    return messages


# Event loop fixture for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
