#!/usr/bin/env python3
"""
Test ContentEnhancer + TelegramPublisher end-to-end with real Telegram.
Tests the full AI enhancement pipeline: Research → Filter → Enhance → Publish
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.content_pipeline import ContentPipeline
from src.core.state_manager import StateManager
from src.publishing.content_enhancer import ContentEnhancer
from src.publishing.telegram_publisher import TelegramPublisher
from src.research.base import BaseResearcher, ContentItem
from src.utils.logger import configure_logging


class MockResearcher(BaseResearcher):
    """Mock researcher that returns test data."""

    def __init__(self):
        super().__init__(source_name="mock_test", max_items=10)

    def score_relevance(self, item: ContentItem) -> float:
        """Score relevance (all test items are highly relevant)."""
        return 9.0

    async def fetch_content(self) -> list[ContentItem]:
        """Return test content items across multiple categories."""
        return [
            # Research papers
            ContentItem(
                source="mock_test",
                title="Revolutionary Multimodal LLM Architecture",
                url=f"https://arxiv.org/abs/2026.{datetime.now().microsecond:05d}",
                category="research",
                relevance_score=9,
                summary="Researchers unveil a breakthrough architecture that achieves state-of-the-art performance on vision-language tasks with 10x fewer parameters.",
                published_date=datetime.now(),
            ),
            ContentItem(
                source="mock_test",
                title="New Scaling Laws for Diffusion Models",
                url=f"https://arxiv.org/abs/2026.{datetime.now().microsecond + 1:05d}",
                category="research",
                relevance_score=9,
                summary="Comprehensive study reveals surprising scaling behavior in diffusion models, suggesting optimal model sizes for different compute budgets.",
                published_date=datetime.now(),
            ),
            ContentItem(
                source="mock_test",
                title="Efficient Fine-Tuning with LoRA Variants",
                url=f"https://arxiv.org/abs/2026.{datetime.now().microsecond + 2:05d}",
                category="research",
                relevance_score=8,
                summary="Novel parameter-efficient fine-tuning methods achieve better performance than standard LoRA while using 50% fewer trainable parameters.",
                published_date=datetime.now(),
            ),
            # News
            ContentItem(
                source="mock_test",
                title="OpenAI Announces GPT-5 with Enhanced Reasoning",
                url=f"https://example.com/news/{datetime.now().microsecond + 3:05d}",
                category="news",
                relevance_score=9,
                summary="Latest model demonstrates significant improvements in mathematical reasoning, code generation, and long-context understanding.",
                published_date=datetime.now(),
            ),
            ContentItem(
                source="mock_test",
                title="Google DeepMind Releases Gemini 2.0 Ultra",
                url=f"https://example.com/news/{datetime.now().microsecond + 4:05d}",
                category="news",
                relevance_score=8,
                summary="New flagship model with advanced multimodal capabilities, native tool use, and improved reasoning performance.",
                published_date=datetime.now(),
            ),
            # Tools
            ContentItem(
                source="mock_test",
                title="LangChain 2.0: Complete Redesign for Production",
                url=f"https://example.com/tools/{datetime.now().microsecond + 5:05d}",
                category="tools",
                relevance_score=8,
                summary="Major framework update focuses on production reliability, better error handling, and simplified agent orchestration.",
                published_date=datetime.now(),
            ),
            ContentItem(
                source="mock_test",
                title="HuggingFace Introduces Zero-Setup Inference API",
                url=f"https://example.com/tools/{datetime.now().microsecond + 6:05d}",
                category="tools",
                relevance_score=7,
                summary="New API allows developers to run any model from the Hub without infrastructure setup or configuration.",
                published_date=datetime.now(),
            ),
            # Business
            ContentItem(
                source="mock_test",
                title="AI Investment Trends Q1 2026",
                url=f"https://example.com/business/{datetime.now().microsecond + 7:05d}",
                category="business",
                relevance_score=7,
                summary="AI startup funding reached $45B in Q1 2026, with infrastructure and enterprise AI tools leading investment categories.",
                published_date=datetime.now(),
            ),
            ContentItem(
                source="mock_test",
                title="Anthropic Raises $2B Series D at $30B Valuation",
                url=f"https://example.com/business/{datetime.now().microsecond + 8:05d}",
                category="business",
                relevance_score=8,
                summary="AI safety company secures major funding round led by strategic investors focused on responsible AI development.",
                published_date=datetime.now(),
            ),
            # Ethics
            ContentItem(
                source="mock_test",
                title="EU AI Act Implementation Guidelines Released",
                url=f"https://example.com/ethics/{datetime.now().microsecond + 9:05d}",
                category="ethics",
                relevance_score=7,
                summary="European Commission publishes detailed compliance framework for AI systems, with phased enforcement beginning in 2027.",
                published_date=datetime.now(),
            ),
        ]


async def main():
    """Run enhanced Telegram publishing test."""

    # Configure logging
    configure_logging(log_level="INFO", pretty_console=True)

    print("=" * 70)
    print("ENHANCED TELEGRAM PUBLISHING TEST")
    print("=" * 70)
    print()

    # Initialize database
    print("1. Initializing database...")
    state_manager = StateManager()
    await state_manager.init_db()
    print("   ✅ Database ready\n")

    # Initialize components
    print("2. Initializing components...")
    researcher = MockResearcher()
    pipeline = ContentPipeline(state_manager)
    enhancer = ContentEnhancer()
    publisher = TelegramPublisher()
    print("   ✅ ContentPipeline ready")
    print("   ✅ ContentEnhancer ready")
    print("   ✅ TelegramPublisher ready\n")

    # Validate Telegram credentials
    print("3. Validating Telegram credentials...")
    if not publisher.validate_credentials():
        print("   ❌ Telegram credentials missing!")
        print("   Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env")
        return

    try:
        me = await publisher.bot.get_me()
        print(f"   ✅ Bot connected: @{me.username}\n")
    except Exception as e:
        print(f"   ❌ Bot connection failed: {e}")
        return

    # Fetch content
    print("4. Fetching content...")
    items = await researcher.research()
    print(f"   ✅ Fetched {len(items)} items\n")

    # Process through pipeline
    print("5. Processing through ContentPipeline...")
    newsletter_date = datetime.now().strftime("%Y-%m-%d-%H")
    newsletter = await pipeline.process(items, newsletter_date)
    print(f"   ✅ Newsletter assembled: {newsletter.item_count} items\n")

    # Display newsletter items before enhancement
    print("📄 Newsletter Items (pre-enhancement):")
    for i, item in enumerate(newsletter.items, 1):
        print(f"{i}. [{item.category}] {item.title[:60]}...")
    print()

    # Enhance with AI
    print("6. Enhancing content with AI agents...")
    print("   → HeadlineWriter (Sonnet)")
    print("   → TakeawayGenerator (Haiku)")
    print("   → EngagementEnricher (local)")
    print("   → SocialFormatter (Haiku)")
    print()

    category_messages, metrics = await enhancer.enhance_newsletter(
        newsletter.items, newsletter_date
    )

    print(f"   ✅ Enhanced {len(category_messages)} categories")
    print(f"   💰 Cost: ${metrics.total_cost:.4f}")
    print(f"   📊 AI enhanced: {metrics.ai_enhanced}/{metrics.total_items}")
    print(f"   📝 Template fallbacks: {metrics.template_fallback}")
    print()

    # Display enhanced categories
    print("📦 Enhanced Categories:")
    for msg in category_messages:
        print(f"  • {msg.category}: {msg.item_count} items")
    print()

    # Publish to Telegram
    print("7. Publishing to Telegram...")
    publish_result = await publisher.publish_enhanced(category_messages)

    print("\n" + "=" * 70)
    if publish_result.success:
        print("✅ PUBLISHING SUCCESS!")
        print("=" * 70)
        print(f"Platform:     {publish_result.platform}")
        print(f"Message:      {publish_result.message}")
        print(f"Total Cost:   ${metrics.total_cost:.4f}")
        print()
        print("🎉 Check your Telegram chat to see the enhanced newsletter!")
        print()
        print("The message should include:")
        print("  • AI-generated engaging headlines")
        print("  • AI-generated key takeaways")
        print("  • Emojis and engagement elements")
        print("  • Content organized by category")
        print("  • Properly formatted Telegram markdown")
    else:
        print("❌ PUBLISHING FAILED!")
        print("=" * 70)
        print(f"Error: {publish_result.error}")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print()


if __name__ == "__main__":
    asyncio.run(main())
