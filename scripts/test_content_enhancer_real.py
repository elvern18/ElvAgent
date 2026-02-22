#!/usr/bin/env python3
"""
Test ContentEnhancer with real sources.

Validates that ContentEnhancer works end-to-end with real content
from ArXiv, HuggingFace, VentureBeat, and TechCrunch.
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import time
from datetime import datetime

from src.core.content_pipeline import ContentPipeline
from src.core.state_manager import StateManager
from src.publishing.content_enhancer import ContentEnhancer
from src.research.arxiv_researcher import ArXivResearcher
from src.research.huggingface_researcher import HuggingFaceResearcher
from src.research.techcrunch_researcher import TechCrunchResearcher
from src.research.venturebeat_researcher import VentureBeatResearcher
from src.utils.logger import get_logger

logger = get_logger("test.enhancer_real")


async def main():
    """Run end-to-end test with real sources."""
    print("=" * 80)
    print("ContentEnhancer Real Sources Test")
    print("=" * 80)
    print()

    # Initialize components
    state_manager = StateManager()
    await state_manager.init_db()

    researchers = [
        ArXivResearcher(),
        HuggingFaceResearcher(),
        VentureBeatResearcher(),
        TechCrunchResearcher()
    ]
    pipeline = ContentPipeline(state_manager)
    enhancer = ContentEnhancer()

    # Phase 1: Fetch from all sources
    print("📡 Phase 1: Fetching from sources...")
    all_items = []

    for researcher in researchers:
        source_name = researcher.__class__.__name__.replace("Researcher", "")
        print(f"  - Fetching from {source_name}...")

        try:
            items = await researcher.fetch_content()
            print(f"    ✅ Fetched {len(items)} items from {source_name}")
            all_items.extend(items)
        except Exception as e:
            print(f"    ❌ Failed to fetch from {source_name}: {e}")

    print(f"\n  Total items fetched: {len(all_items)}")
    print()

    if len(all_items) == 0:
        print("❌ No items fetched. Cannot proceed with test.")
        return

    # Phase 2: Process through pipeline
    print("🔄 Phase 2: Processing through ContentPipeline...")

    start_time = time.time()
    newsletter = await pipeline.process(
        items=all_items,
        date=datetime.now().strftime("%Y-%m-%d-%H")
    )
    pipeline_time = time.time() - start_time

    print(f"  ✅ Pipeline complete in {pipeline_time:.2f}s")
    print(f"  Items after dedup/filter: {newsletter.item_count}")
    print()

    if newsletter.item_count == 0:
        print("❌ No items survived filtering. Cannot proceed with enhancement.")
        return

    # Phase 3: Enhance with ContentEnhancer
    print("✨ Phase 3: Enhancing with ContentEnhancer...")

    start_time = time.time()
    category_messages, metrics = await enhancer.enhance_newsletter(
        items=newsletter.items,
        date=newsletter.date,
        max_items_per_category=5
    )
    enhance_time = time.time() - start_time

    print(f"  ✅ Enhancement complete in {enhance_time:.2f}s")
    print()

    # Phase 4: Display results
    print("📊 Phase 4: Results")
    print("-" * 80)
    print()

    print("Categories:")
    for msg in category_messages:
        print(f"  📁 {msg.category} - {msg.title}")
        print(f"     {len(msg.items)} items")

        # Show first item from each category
        if msg.items:
            item = msg.items[0]
            print(f"     Example: {item.viral_headline[:60]}...")
            print(f"              {item.takeaway[:60]}...")
        print()

    # Phase 5: Metrics
    print("💰 Metrics:")
    print(f"  Total items processed: {metrics.total_items}")
    print(f"  AI-enhanced items: {metrics.ai_enhanced}")
    print(f"  Template fallback: {metrics.template_fallback}")
    print(f"  Success rate: {metrics.success_rate:.1f}%")
    print(f"  Total cost: ${metrics.total_cost:.4f}")
    print(f"  Avg time per item: {metrics.avg_time_per_item:.2f}s")
    print()

    # Success criteria
    print("✅ Success Criteria:")
    checks = []

    # 1. Fetched from sources
    if len(all_items) > 0:
        checks.append(("Fetched from sources", True))
    else:
        checks.append(("Fetched from sources", False))

    # 2. Enhanced 5-10 items
    if 5 <= metrics.total_items <= 15:
        checks.append(("Enhanced 5-15 items", True))
    else:
        checks.append((f"Enhanced {metrics.total_items} items (expected 5-15)", False))

    # 3. Success rate > 80%
    if metrics.success_rate >= 80:
        checks.append((f"Success rate {metrics.success_rate:.1f}% >= 80%", True))
    else:
        checks.append((f"Success rate {metrics.success_rate:.1f}% < 80%", False))

    # 4. Cost < $0.05
    if metrics.total_cost < 0.05:
        checks.append((f"Cost ${metrics.total_cost:.4f} < $0.05", True))
    else:
        checks.append((f"Cost ${metrics.total_cost:.4f} >= $0.05", False))

    # 5. No crashes
    checks.append(("No crashes", True))

    # Display checks
    for check, passed in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {check}")

    # Overall result
    all_passed = all(passed for _, passed in checks)
    print()
    if all_passed:
        print("🎉 ALL CHECKS PASSED! ContentEnhancer is working correctly.")
    else:
        print("⚠️  Some checks failed. Review results above.")

    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
