"""
Unit tests for StateManager.
"""
import pytest
from datetime import date


@pytest.mark.unit
@pytest.mark.asyncio
async def test_init_db(state_manager):
    """Test database initialization."""
    import aiosqlite

    # Database should be initialized by the fixture
    # Just verify we can query it
    async with aiosqlite.connect(state_manager.db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = await cursor.fetchall()
        table_names = [row[0] for row in tables]

    expected_tables = [
        'published_items',
        'newsletters',
        'publishing_logs',
        'api_metrics',
        'content_fingerprints'
    ]

    for table in expected_tables:
        assert table in table_names, f"Table {table} not created"


@pytest.mark.unit
def test_generate_content_id(state_manager):
    """Test content ID generation."""
    content_id = state_manager.generate_content_id(
        url="https://example.com/article",
        title="Test Article"
    )

    # Should be a SHA-256 hash (64 hex characters)
    assert len(content_id) == 64
    assert all(c in '0123456789abcdef' for c in content_id)

    # Same input should produce same hash
    content_id2 = state_manager.generate_content_id(
        url="https://example.com/article",
        title="Test Article"
    )
    assert content_id == content_id2

    # Different input should produce different hash
    content_id3 = state_manager.generate_content_id(
        url="https://example.com/different",
        title="Different Article"
    )
    assert content_id != content_id3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_duplicate_not_exists(state_manager):
    """Test duplicate check when content doesn't exist."""
    is_dup = await state_manager.check_duplicate(
        url="https://example.com/new",
        title="New Article"
    )

    assert is_dup is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_duplicate_exists(state_manager):
    """Test duplicate check when content exists."""
    # Store a fingerprint
    await state_manager.store_fingerprint(
        url="https://example.com/existing",
        title="Existing Article",
        source="test"
    )

    # Check should now return True
    is_dup = await state_manager.check_duplicate(
        url="https://example.com/existing",
        title="Existing Article"
    )

    assert is_dup is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_store_content(state_manager):
    """Test storing content item."""
    item = {
        "url": "https://arxiv.org/abs/2024.12345",
        "title": "Test Paper",
        "source": "arxiv",
        "category": "research",
        "newsletter_date": "2026-02-15-10",
        "metadata": {"authors": ["John Doe"]}
    }

    row_id = await state_manager.store_content(item)

    assert row_id > 0

    # Verify it's now a duplicate
    is_dup = await state_manager.check_duplicate(
        url=item["url"],
        title=item["title"]
    )
    assert is_dup is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_newsletter_record(state_manager):
    """Test creating newsletter record."""
    newsletter_id = await state_manager.create_newsletter_record(
        newsletter_date="2026-02-15-10",
        item_count=5,
        platforms_published=["discord", "twitter"],
        skip_reason=None
    )

    assert newsletter_id > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_log_publishing_attempt(state_manager):
    """Test logging publishing attempt."""
    # First create a newsletter
    newsletter_id = await state_manager.create_newsletter_record(
        newsletter_date="2026-02-15-10",
        item_count=5,
        platforms_published=["discord"]
    )

    # Log publishing attempt
    await state_manager.log_publishing_attempt(
        newsletter_id=newsletter_id,
        platform="discord",
        status="success",
        error_message=None,
        attempt_count=1
    )

    # Should complete without error


@pytest.mark.unit
@pytest.mark.asyncio
async def test_track_api_usage(state_manager):
    """Test tracking API usage."""
    await state_manager.track_api_usage(
        api_name="anthropic",
        request_count=5,
        token_count=1000,
        estimated_cost=0.003
    )

    metrics = await state_manager.get_metrics()

    assert "anthropic" in metrics
    assert metrics["anthropic"]["requests"] == 5
    assert metrics["anthropic"]["tokens"] == 1000
    assert metrics["anthropic"]["cost"] == 0.003


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_metrics_empty(state_manager):
    """Test getting metrics when none exist."""
    metrics = await state_manager.get_metrics()

    assert isinstance(metrics, dict)
    assert metrics.get("total_cost", 0) == 0
