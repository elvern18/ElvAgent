#!/usr/bin/env python3
"""
Test full pipeline with mock ArXiv data and real Twitter posting.
This simulates finding real papers and tests the complete flow.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import ContentPipeline, Orchestrator, StateManager
from src.publishing.markdown_publisher import MarkdownPublisher
from src.publishing.twitter_publisher import TwitterPublisher
from src.research.base import ContentItem
from src.utils.logger import configure_logging


async def test_full_pipeline():
    """Test full pipeline with mock research data."""

    # Configure logging
    configure_logging(log_level="INFO", pretty_console=True)

    print("=" * 60)
    print("Testing Full Pipeline with Mock Data + Real Twitter")
    print("=" * 60)

    # Initialize database
    print("\n1. Initializing database...")
    state_manager = StateManager()
    await state_manager.init_db()

    # Create mock researcher that returns sample data
    print("\n2. Creating mock researcher with sample AI papers...")

    class MockResearcher:
        def __init__(self):
            self.source_name = "mock_arxiv"

        async def research(self):
            """Return mock AI papers."""
            now = datetime.now()
            return [
                ContentItem(
                    title="Efficient Attention Mechanisms for Long-Context Transformers",
                    url="https://arxiv.org/abs/2024.01234",
                    source="arxiv",
                    category="research",
                    relevance_score=9,
                    summary="This paper introduces a novel attention mechanism that reduces computational complexity from O(n²) to O(n log n) while maintaining performance on long-context tasks.",
                    published_date=now,
                    metadata={"authors": ["Smith, J.", "Chen, L."]},
                ),
                ContentItem(
                    title="Multimodal Reasoning with Vision-Language Models",
                    url="https://arxiv.org/abs/2024.05678",
                    source="arxiv",
                    category="research",
                    relevance_score=8,
                    summary="We present a new approach to multimodal reasoning that achieves state-of-the-art results on VQA, image captioning, and visual reasoning benchmarks.",
                    published_date=now,
                    metadata={"authors": ["Wang, Y.", "Johnson, M."]},
                ),
                ContentItem(
                    title="Scaling Laws for Diffusion Models",
                    url="https://arxiv.org/abs/2024.09876",
                    source="arxiv",
                    category="research",
                    relevance_score=8,
                    summary="Analysis of scaling behavior in diffusion models reveals predictable relationships between model size, training compute, and generation quality.",
                    published_date=now,
                    metadata={"authors": ["Brown, A."]},
                ),
            ]

    # Initialize components
    print("\n3. Initializing pipeline components...")
    researchers = [MockResearcher()]
    publishers = [TwitterPublisher(), MarkdownPublisher()]
    pipeline = ContentPipeline(state_manager)

    # Create orchestrator
    orchestrator = Orchestrator(
        state_manager=state_manager,
        researchers=researchers,
        publishers=publishers,
        pipeline=pipeline,
    )

    # Show what will be generated
    print("\n4. Running research phase...")
    items = await orchestrator.research_phase()
    print(f"   Found {len(items)} papers")

    print("\n5. Running filter phase...")
    newsletter = await orchestrator.filter_phase(items)
    print(f"   Generated newsletter with {newsletter.item_count} items")
    print(f"\n   Summary: {newsletter.summary}")

    # Format for Twitter to show preview
    print("\n6. Formatting for Twitter...")
    twitter_pub = publishers[0]
    tweets = await twitter_pub.format_content(newsletter)

    print(f"\n📝 Generated {len(tweets)} tweets:")
    for i, tweet in enumerate(tweets, 1):
        print(f"\n--- Tweet {i} ({len(tweet)} chars) ---")
        print(tweet)

    # Ask for confirmation
    print("\n" + "=" * 60)
    print("⚠️  READY TO POST FULL PIPELINE TEST")
    print("=" * 60)
    print("This will:")
    print("  - Post newsletter thread to Twitter")
    print("  - Save markdown file")
    print("  - Store records in database")
    print("  - Track API costs")
    response = input("\nProceed with full test? (yes/no): ")

    if response.lower() != "yes":
        print("\n❌ Aborted. No changes made.")
        return

    # Run publish phase
    print("\n7. Running publish phase...")
    publish_results = await orchestrator.publish_phase(newsletter)

    # Show results
    print("\n" + "=" * 60)
    print("📊 PUBLISH RESULTS")
    print("=" * 60)

    for result in publish_results:
        if result.success:
            print(f"✅ {result.platform}: {result.message}")
            if result.metadata and "thread_url" in result.metadata:
                print(f"   URL: {result.metadata['thread_url']}")
        else:
            print(f"❌ {result.platform}: {result.error}")

    # Run record phase
    print("\n8. Running record phase...")
    await orchestrator.record_phase(newsletter, publish_results)

    # Get metrics
    print("\n9. Checking metrics...")
    metrics = await state_manager.get_metrics()
    print(f"   Total cost today: ${metrics.get('total_cost', 0):.4f}")

    print("\n" + "=" * 60)
    print("✅ FULL PIPELINE TEST COMPLETE!")
    print("=" * 60)
    print("\nCheck:")
    print("  - Your Twitter account for the thread")
    print("  - data/newsletters/ for markdown file")
    print("  - Database: sqlite3 data/state.db 'SELECT * FROM newsletters;'")
    print()


if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
