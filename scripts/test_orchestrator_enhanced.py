#!/usr/bin/env python3
"""
Test Orchestrator with ContentEnhancement enabled.

Validates full orchestrator cycle with AI content enhancement.
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio

from src.config.settings import settings
from src.core.content_pipeline import ContentPipeline
from src.core.orchestrator import Orchestrator
from src.core.state_manager import StateManager
from src.publishing.markdown_publisher import MarkdownPublisher
from src.publishing.telegram_publisher import TelegramPublisher
from src.research.arxiv_researcher import ArXivResearcher
from src.research.huggingface_researcher import HuggingFaceResearcher
from src.utils.logger import get_logger

logger = get_logger("test.orchestrator_enhanced")


async def main():
    """Run full orchestrator cycle with enhancement."""
    print("=" * 80)
    print("Orchestrator Enhanced Test")
    print("=" * 80)
    print()

    # Override settings for test
    settings.enable_content_enhancement = True
    settings.max_items_per_category = 5

    print(f"Enhancement enabled: {settings.enable_content_enhancement}")
    print(f"Max items per category: {settings.max_items_per_category}")
    print()

    # Initialize components
    state_manager = StateManager()
    await state_manager.init_db()

    researchers = [
        ArXivResearcher(max_items=5),
        HuggingFaceResearcher(max_items=5)
    ]

    publishers = [
        TelegramPublisher(),
        MarkdownPublisher()
    ]

    pipeline = ContentPipeline(state_manager)

    orchestrator = Orchestrator(
        state_manager=state_manager,
        researchers=researchers,
        publishers=publishers,
        pipeline=pipeline
    )

    # Run cycle in test mode (no actual publishing)
    print("🚀 Running orchestrator cycle (test mode)...")
    print()

    result = await orchestrator.run_cycle(mode="test")

    # Display results
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()

    print(f"Success: {result.success}")
    print(f"Items fetched: {result.item_count}")
    print(f"Items filtered: {result.filtered_count}")
    print(f"Total cost: ${result.total_cost:.4f}")
    print()

    if result.enhancement_enabled and result.enhancement_metrics:
        print("✨ ENHANCEMENT METRICS:")
        metrics = result.enhancement_metrics
        print(f"  Total items enhanced: {metrics.total_items}")
        print(f"  AI-enhanced: {metrics.ai_enhanced}")
        print(f"  Template fallback: {metrics.template_fallback}")
        print(f"  Success rate: {metrics.success_rate:.1f}%")
        print(f"  Enhancement cost: ${metrics.total_cost:.4f}")
        print(f"  Avg time per item: {metrics.avg_time_per_item:.2f}s")
        print()
    else:
        print("⚠️  Enhancement was not enabled or no metrics available")
        print()

    if result.newsletter:
        print("📰 NEWSLETTER:")
        print(f"  Date: {result.newsletter.date}")
        print(f"  Items: {result.newsletter.item_count}")
        print(f"  Summary: {result.newsletter.summary[:100]}...")
        print()

    # Verification
    print("✅ VERIFICATION:")
    checks = []

    # 1. Cycle succeeded
    checks.append(("Cycle completed successfully", result.success))

    # 2. Enhancement was enabled
    checks.append(("Enhancement enabled", result.enhancement_enabled))

    # 3. Got some items
    if result.filtered_count > 0:
        checks.append((f"Filtered {result.filtered_count} items", True))
    else:
        checks.append(("Got filtered items", False))

    # 4. Enhancement metrics exist
    if result.enhancement_metrics:
        checks.append(("Enhancement metrics available", True))
    else:
        checks.append(("Enhancement metrics available", False))

    # 5. Cost is reasonable
    if result.total_cost < 0.20:
        checks.append((f"Cost ${result.total_cost:.4f} < $0.20", True))
    else:
        checks.append((f"Cost ${result.total_cost:.4f} >= $0.20", False))

    # Display checks
    for check, passed in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {check}")

    # Overall result
    all_passed = all(passed for _, passed in checks)
    print()
    if all_passed:
        print("🎉 ALL CHECKS PASSED! Orchestrator enhancement integration working.")
    else:
        print("⚠️  Some checks failed. Review results above.")

    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
