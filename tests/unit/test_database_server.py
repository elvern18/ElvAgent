"""
Unit tests for Database MCP Server.
"""
import pytest
from unittest.mock import AsyncMock, Mock
from src.mcp_servers.database_server import DatabaseServer


@pytest.mark.unit
@pytest.mark.asyncio
async def test_server_initialization(temp_dir):
    """Test that DatabaseServer initializes correctly."""
    db_path = temp_dir / "test_mcp.db"
    server = DatabaseServer(db_path=db_path)

    assert server.db_path == db_path
    assert server.state_manager is not None
    assert server.server is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_duplicate_not_exists(temp_dir):
    """Test check_duplicate when content doesn't exist."""
    db_path = temp_dir / "test_mcp.db"
    server = DatabaseServer(db_path=db_path)
    await server.state_manager.init_db()

    result = await server._check_duplicate(
        url="https://example.com/new",
        title="New Article"
    )

    assert result["is_duplicate"] is False
    assert "content_id" in result
    assert len(result["content_id"]) == 64  # SHA-256 hash
    assert "first_seen" not in result  # Not present for new content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_duplicate_exists(temp_dir):
    """Test check_duplicate when content exists."""
    db_path = temp_dir / "test_mcp.db"
    server = DatabaseServer(db_path=db_path)
    await server.state_manager.init_db()

    # Store a fingerprint first
    await server.state_manager.store_fingerprint(
        url="https://example.com/existing",
        title="Existing Article",
        source="test"
    )

    result = await server._check_duplicate(
        url="https://example.com/existing",
        title="Existing Article"
    )

    assert result["is_duplicate"] is True
    assert "content_id" in result
    assert "first_seen" in result  # Should include timestamp


@pytest.mark.unit
@pytest.mark.asyncio
async def test_store_content_success(temp_dir):
    """Test storing content successfully."""
    db_path = temp_dir / "test_mcp.db"
    server = DatabaseServer(db_path=db_path)
    await server.state_manager.init_db()

    item = {
        "url": "https://arxiv.org/abs/2026.12345",
        "title": "Test Paper",
        "source": "arxiv",
        "category": "research",
        "newsletter_date": "2026-02-15-10",
        "metadata": {"authors": ["John Doe"]}
    }

    result = await server._store_content(item)

    assert result["success"] is True
    assert "row_id" in result
    assert result["row_id"] > 0
    assert "content_id" in result
    assert len(result["content_id"]) == 64


@pytest.mark.unit
@pytest.mark.asyncio
async def test_store_content_missing_fields(temp_dir):
    """Test store_content with missing required fields."""
    db_path = temp_dir / "test_mcp.db"
    server = DatabaseServer(db_path=db_path)
    await server.state_manager.init_db()

    item = {
        "url": "https://example.com/test"
        # Missing title and source
    }

    result = await server._store_content(item)

    assert result["success"] is False
    assert "error" in result
    assert "Missing required field" in result["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_metrics_empty(temp_dir):
    """Test get_metrics with no data."""
    db_path = temp_dir / "test_mcp.db"
    server = DatabaseServer(db_path=db_path)
    await server.state_manager.init_db()

    result = await server._get_metrics()

    assert "date" in result
    assert "metrics" in result
    assert result["total_cost"] == 0.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_metrics_with_data(temp_dir):
    """Test get_metrics with actual data."""
    db_path = temp_dir / "test_mcp.db"
    server = DatabaseServer(db_path=db_path)
    await server.state_manager.init_db()

    # Track some usage
    await server.state_manager.track_api_usage(
        api_name="anthropic",
        request_count=5,
        token_count=1000,
        estimated_cost=0.003
    )

    result = await server._get_metrics()

    assert result["total_cost"] == 0.003
    assert "anthropic" in result["metrics"]
    assert result["metrics"]["anthropic"]["requests"] == 5
