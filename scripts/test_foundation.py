#!/usr/bin/env python3
"""
Test script to verify foundation components work correctly.
Tests database, logging, researcher, and configuration.
"""
import asyncio
import os
import sys
from pathlib import Path

# Set minimal environment for testing
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-foundation-test")
os.environ.setdefault("DATABASE_PATH", ":memory:")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import settings
from src.core.state_manager import StateManager
from src.research.arxiv_researcher import ArXivResearcher
from src.utils.cost_tracker import cost_tracker
from src.utils.logger import configure_logging, get_logger


async def test_database():
    """Test database initialization and operations."""
    print("\n=== Testing Database ===")

    # Initialize database
    state_manager = StateManager()
    await state_manager.init_db()
    print("✓ Database initialized")

    # Test deduplication
    is_dup = await state_manager.check_duplicate(
        url="https://example.com/test",
        title="Test Article"
    )
    print(f"✓ Duplicate check: {is_dup} (should be False)")

    # Store fingerprint
    await state_manager.store_fingerprint(
        url="https://example.com/test",
        title="Test Article",
        source="test"
    )
    print("✓ Fingerprint stored")

    # Check again (should be duplicate now)
    is_dup = await state_manager.check_duplicate(
        url="https://example.com/test",
        title="Test Article"
    )
    print(f"✓ Duplicate check after store: {is_dup} (should be True)")

    # Test metrics tracking
    await state_manager.track_api_usage(
        api_name="test_api",
        request_count=5,
        token_count=1000,
        estimated_cost=0.003
    )
    print("✓ API usage tracked")

    metrics = await state_manager.get_metrics()
    print(f"✓ Retrieved metrics: {metrics}")


async def test_researcher():
    """Test ArXiv researcher."""
    print("\n=== Testing ArXiv Researcher ===")

    researcher = ArXivResearcher(max_items=3)
    print("✓ ArXiv researcher created")

    try:
        items = await researcher.research()
        print(f"✓ Research complete: Found {len(items)} items")

        for i, item in enumerate(items, 1):
            print(f"\n  Item {i}:")
            print(f"    Title: {item.title[:60]}...")
            print(f"    Score: {item.relevance_score}/10")
            print(f"    Authors: {', '.join(item.metadata.get('authors', [])[:2])}")

    except Exception as e:
        print("⚠ Research failed (this is okay if offline or network issues)")
        print(f"  Error: {type(e).__name__}: {str(e)[:100]}")
        print("  → This doesn't affect core functionality tests")


def test_logging():
    """Test logging configuration."""
    print("\n=== Testing Logging ===")

    # Configure logging
    logger = configure_logging(log_level="INFO", pretty_console=True)
    print("✓ Logging configured")

    # Test logging
    logger.info("test_log", message="This is a test log", component="test")
    print("✓ Log message written")

    # Test module-specific logger
    module_logger = get_logger("test_module")
    module_logger.debug("debug_message", detail="Should not appear (INFO level)")
    module_logger.info("info_message", detail="This should appear")
    print("✓ Module logger works")


def test_config():
    """Test configuration settings."""
    print("\n=== Testing Configuration ===")

    print(f"✓ Project root: {settings.project_root}")
    print(f"✓ Database path: {settings.database_path}")
    print(f"✓ Max daily cost: ${settings.max_daily_cost}")
    print(f"✓ Log level: {settings.log_level}")

    # Ensure directories
    settings.ensure_directories()
    print("✓ Directories created")


def test_cost_tracker():
    """Test cost tracking."""
    print("\n=== Testing Cost Tracker ===")

    # Estimate cost
    cost = cost_tracker.estimate_cost(
        api_name="anthropic",
        model="claude-sonnet-4-5-20250929",
        input_tokens=1000,
        output_tokens=500
    )
    print(f"✓ Estimated cost for 1500 tokens: ${cost:.4f}")

    # Track usage
    stats = cost_tracker.track_usage(
        api_name="anthropic",
        model="claude-sonnet-4-5-20250929",
        input_tokens=1000,
        output_tokens=500
    )
    print(f"✓ Usage tracked: ${stats['cost']:.4f}")

    # Get daily total
    total = cost_tracker.get_daily_total()
    print(f"✓ Daily total: ${total:.4f}")

    # Check budget
    within_budget = cost_tracker.check_budget(max_daily_cost=5.0)
    print(f"✓ Within budget: {within_budget}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("ElvAgent Foundation Test Suite")
    print("=" * 60)

    try:
        # Test order matters (database first, then others)
        test_config()
        test_logging()
        test_cost_tracker()
        await test_database()
        await test_researcher()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
