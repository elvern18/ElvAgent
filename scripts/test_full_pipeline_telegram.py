#!/usr/bin/env python3
"""
Full end-to-end pipeline test for Telegram.
Tests: Research → Filter → Assemble → Publish to Telegram
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.content_pipeline import ContentPipeline
from src.core.orchestrator import Orchestrator
from src.core.state_manager import StateManager
from src.publishing.markdown_publisher import MarkdownPublisher
from src.publishing.telegram_publisher import TelegramPublisher
from src.research.base import BaseResearcher, ContentItem
from src.utils.logger import configure_logging


class MockResearcher(BaseResearcher):
    """Mock researcher that returns test data."""

    def __init__(self):
        super().__init__(source_name="mock_test", max_items=5)

    def score_relevance(self, item: ContentItem) -> float:
        """Score relevance (all test items are highly relevant)."""
        return 9.0

    async def fetch_content(self) -> list[ContentItem]:
        """Return test content items."""
        return [
            ContentItem(
                source="mock_test",
                title="🚀 Revolutionary Multimodal LLM Architecture Released",
                url=f"https://arxiv.org/abs/2026.{datetime.now().microsecond:05d}",
                category="research",
                relevance_score=9,
                summary="Researchers unveil a breakthrough architecture that achieves state-of-the-art performance on vision-language tasks with 10x fewer parameters than existing models.",
                published_date=datetime.now(),
            ),
            ContentItem(
                source="mock_test",
                title="🔬 New Scaling Laws for Diffusion Models",
                url=f"https://arxiv.org/abs/2026.{datetime.now().microsecond + 1:05d}",
                category="research",
                relevance_score=9,
                summary="Comprehensive study reveals surprising scaling behavior in diffusion models, suggesting optimal model sizes for different compute budgets.",
                published_date=datetime.now(),
            ),
            ContentItem(
                source="mock_test",
                title="🤖 OpenAI Announces GPT-5 with Enhanced Reasoning",
                url=f"https://example.com/news/{datetime.now().microsecond:05d}",
                category="news",
                relevance_score=8,
                summary="Latest model demonstrates significant improvements in mathematical reasoning, code generation, and long-context understanding.",
                published_date=datetime.now(),
            ),
            ContentItem(
                source="mock_test",
                title="📊 Analysis: AI Investment Trends Q1 2026",
                url=f"https://example.com/analysis/{datetime.now().microsecond:05d}",
                category="business",
                relevance_score=7,
                summary="AI startup funding reached $45B in Q1 2026, with infrastructure and enterprise AI tools leading investment categories.",
                published_date=datetime.now(),
            ),
        ]


async def main():
    """Run full end-to-end pipeline test."""

    # Configure logging
    configure_logging(log_level="INFO", pretty_console=True)

    print("=" * 70)
    print("FULL END-TO-END PIPELINE TEST - TELEGRAM")
    print("=" * 70)
    print()

    # Initialize database
    print("1. Initializing database...")
    state_manager = StateManager()
    await state_manager.init_db()
    print("   ✅ Database ready\n")

    # Initialize components
    print("2. Initializing components...")
    researchers = [MockResearcher()]
    publishers = [TelegramPublisher(), MarkdownPublisher()]
    pipeline = ContentPipeline(state_manager)
    print(f"   ✅ Researchers: {len(researchers)}")
    print(f"   ✅ Publishers: {len(publishers)}\n")

    # Validate Telegram credentials
    print("3. Validating Telegram credentials...")
    telegram_pub = publishers[0]
    if not telegram_pub.validate_credentials():
        print("   ❌ Telegram credentials missing!")
        print("   Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env")
        return

    try:
        me = await telegram_pub.bot.get_me()
        print(f"   ✅ Bot connected: @{me.username}\n")
    except Exception as e:
        print(f"   ❌ Bot connection failed: {e}")
        return

    # Create orchestrator
    print("4. Creating orchestrator...")
    orchestrator = Orchestrator(
        state_manager=state_manager,
        researchers=researchers,
        publishers=publishers,
        pipeline=pipeline,
    )
    print("   ✅ Orchestrator ready\n")

    # Run full cycle
    print("5. Running full pipeline cycle...")
    print("   → Fetching content from mock researcher")
    print("   → Filtering duplicates")
    print("   → Scoring and ranking items")
    print("   → Assembling newsletter")
    print("   → Publishing to platforms")
    print()

    result = await orchestrator.run_cycle(mode="production")

    # Display results
    print("\n" + "=" * 70)
    if result.success:
        print("✅ PIPELINE SUCCESS!")
        print("=" * 70)
        print(f"Items found:     {result.item_count}")
        print(f"Items filtered:  {result.filtered_count}")
        print(f"Platforms:       {', '.join(result.platforms_published)}")
        print(f"Cost:            ${result.total_cost:.4f}")

        if result.newsletter:
            print(f"\nNewsletter Date: {result.newsletter.date}")
            print(f"Items in Newsletter: {result.newsletter.item_count}")
            print(f"\nSummary:\n{result.newsletter.summary}")

            print("\n📄 Newsletter Items:")
            for i, item in enumerate(result.newsletter.items, 1):
                print(f"\n{i}. {item.title}")
                print(f"   Category: {item.category} | Score: {item.relevance_score}")
                print(f"   {item.summary[:100]}...")

        print("\n📊 Publishing Results:")
        for pub_result in result.publish_results:
            status = "✅" if pub_result.success else "❌"
            print(f"  {status} {pub_result.platform}: {pub_result.message}")
            if pub_result.error:
                print(f"     Error: {pub_result.error}")

        print("\n🎉 Check your Telegram chat to see the published newsletter!")

    else:
        print("❌ PIPELINE FAILED!")
        print("=" * 70)
        print(f"Error: {result.error}")

    print("\n")


if __name__ == "__main__":
    asyncio.run(main())
