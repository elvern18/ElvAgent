"""
Pytest configuration and shared fixtures.
"""
import asyncio
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock

# Set test environment variables before importing settings
os.environ["DATABASE_PATH"] = ":memory:"  # Use in-memory SQLite for tests
os.environ["LOG_LEVEL"] = "WARNING"  # Reduce noise in tests
os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"  # Mock API key for tests

from src.config.settings import Settings
from src.core.state_manager import StateManager
from src.research.arxiv_researcher import ArXivResearcher


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
        log_level="WARNING"
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
    from src.research.base import ContentItem
    from datetime import datetime

    return [
        ContentItem(
            title="Novel LLM Architecture",
            url="https://arxiv.org/abs/2024.12345",
            source="arxiv",
            category="research",
            relevance_score=9,
            summary="A breakthrough in LLM architecture...",
            metadata={"authors": ["John Doe", "Jane Smith"]},
            published_date=datetime(2026, 2, 15, 10, 0)
        ),
        ContentItem(
            title="New Multimodal Model",
            url="https://huggingface.co/papers/abc123",
            source="huggingface",
            category="research",
            relevance_score=8,
            summary="Combining vision and language...",
            metadata={"downloads": 10000},
            published_date=datetime(2026, 2, 15, 9, 0)
        ),
        ContentItem(
            title="AI Startup Raises $100M",
            url="https://techcrunch.com/funding/xyz",
            source="techcrunch",
            category="funding",
            relevance_score=7,
            summary="Seed funding for AI infrastructure...",
            metadata={"amount": "100M", "investors": ["a16z"]},
            published_date=datetime(2026, 2, 15, 8, 0)
        ),
    ]


@pytest.fixture
def mock_newsletter_data():
    """Sample newsletter data for testing publishers."""
    return {
        "date": "2026-02-15-10",
        "items": [
            {
                "title": "Novel LLM Architecture",
                "url": "https://arxiv.org/abs/2024.12345",
                "summary": "Breakthrough in reasoning...",
                "category": "research"
            },
            {
                "title": "AI Startup Raises $100M",
                "url": "https://techcrunch.com/funding/xyz",
                "summary": "Major funding round...",
                "category": "funding"
            }
        ],
        "summary": "Today's AI highlights include a novel LLM architecture and major funding.",
        "item_count": 2
    }


# Event loop fixture for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
