#!/usr/bin/env python3
"""
Test script to verify MCP server can be initialized and queried.
"""
import asyncio
import sys
import os
import tempfile
from pathlib import Path

# Set test environment
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mcp_servers.database_server import DatabaseServer


async def test_mcp_server():
    """Test MCP server initialization and basic functionality."""
    print("=" * 60)
    print("MCP Server Test")
    print("=" * 60)

    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_db_path = Path(temp_db.name)
    temp_db.close()

    try:
        # Initialize server
        print("\n=== Initializing MCP Server ===")
        server = DatabaseServer(db_path=temp_db_path)
        print(f"✓ Server created")
        print(f"  Database path: {server.db_path}")
        print(f"  State manager: {server.state_manager}")

        # Initialize database
        print("\n=== Initializing Database ===")
        await server.state_manager.init_db()
        print("✓ Database initialized")

        # Test check_duplicate tool
        print("\n=== Testing check_duplicate Tool ===")
        result = await server._check_duplicate(
            url="https://example.com/test",
            title="Test Article"
        )
        print(f"✓ check_duplicate result: {result}")
        assert result["is_duplicate"] is False
        assert len(result["content_id"]) == 64
        print("  ✓ Returns correct structure")
        print("  ✓ Content ID is valid SHA-256 hash")

        # Test store_content tool
        print("\n=== Testing store_content Tool ===")
        item = {
            "url": "https://arxiv.org/abs/2026.12345",
            "title": "Test Paper",
            "source": "arxiv",
            "category": "research",
            "newsletter_date": "2026-02-15-10"
        }
        result = await server._store_content(item)
        print(f"✓ store_content result: {result}")
        assert result["success"] is True
        assert result["row_id"] > 0
        print("  ✓ Content stored successfully")
        print(f"  ✓ Row ID: {result['row_id']}")

        # Test duplicate detection after storage
        print("\n=== Testing Duplicate Detection ===")
        result = await server._check_duplicate(
            url="https://arxiv.org/abs/2026.12345",
            title="Test Paper"
        )
        print(f"✓ check_duplicate (after store) result: {result}")
        assert result["is_duplicate"] is True
        assert "first_seen" in result
        print("  ✓ Duplicate detected correctly")
        print(f"  ✓ First seen: {result['first_seen']}")

        # Test get_metrics tool
        print("\n=== Testing get_metrics Tool ===")
        # Track some usage first
        await server.state_manager.track_api_usage(
            api_name="test_api",
            request_count=10,
            token_count=5000,
            estimated_cost=0.015
        )
        result = await server._get_metrics()
        print(f"✓ get_metrics result: {result}")
        assert "metrics" in result
        assert result["total_cost"] > 0
        print("  ✓ Metrics retrieved successfully")
        print(f"  ✓ Total cost: ${result['total_cost']:.4f}")

        # Test error handling
        print("\n=== Testing Error Handling ===")
        result = await server._store_content({"url": "missing-title"})
        print(f"✓ store_content (invalid) result: {result}")
        assert result["success"] is False
        assert "error" in result
        print("  ✓ Validation error handled correctly")

        print("\n" + "=" * 60)
        print("✓ All MCP Server Tests Passed!")
        print("=" * 60)
        print("\nThe MCP server is ready to use with Claude!")
        print("Run it with: python -m src.mcp_servers.database_server")

    finally:
        # Cleanup temp database
        if temp_db_path.exists():
            temp_db_path.unlink()


if __name__ == "__main__":
    asyncio.run(test_mcp_server())
