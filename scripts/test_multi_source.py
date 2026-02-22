"""
Integration test for multi-source research.
Tests all 4 researchers working together.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.research.arxiv_researcher import ArXivResearcher
from src.research.huggingface_researcher import HuggingFaceResearcher
from src.research.techcrunch_researcher import TechCrunchResearcher
from src.research.venturebeat_researcher import VentureBeatResearcher


async def test_multi_source():
    """Test all researchers in parallel."""
    print("=" * 80)
    print("Testing Multi-Source Research (Parallel)")
    print("=" * 80)

    # Create all researchers
    researchers = [
        ArXivResearcher(max_items=5),
        HuggingFaceResearcher(max_items=5),
        VentureBeatResearcher(max_items=5),
        TechCrunchResearcher(max_items=5),
    ]

    # Run all researchers in parallel
    print("\nFetching content from 4 sources in parallel...\n")
    results = await asyncio.gather(
        *[researcher.research() for researcher in researchers], return_exceptions=True
    )

    # Analyze results
    all_items = []
    source_stats = {}

    for researcher, items in zip(researchers, results, strict=False):
        if isinstance(items, Exception):
            print(f"❌ {researcher.source_name}: Error - {items}")
            source_stats[researcher.source_name] = {"count": 0, "error": str(items)}
        else:
            print(f"✅ {researcher.source_name}: {len(items)} items")
            all_items.extend(items)
            source_stats[researcher.source_name] = {
                "count": len(items),
                "categories": set(item.category for item in items),
                "avg_score": sum(item.relevance_score for item in items) / len(items)
                if items
                else 0,
            }

    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print(f"Total items fetched: {len(all_items)}")
    print(f"Sources that succeeded: {sum(1 for s in source_stats.values() if s['count'] > 0)}/4")

    print("\nBreakdown by source:")
    for source, stats in source_stats.items():
        if "error" not in stats:
            print(f"  {source}: {stats['count']} items, avg score: {stats['avg_score']:.1f}/10")
            print(f"    Categories: {', '.join(stats['categories'])}")

    # Category diversity
    all_categories = set(item.category for item in all_items)
    print(f"\nCategory diversity: {len(all_categories)} categories")
    print(f"  Categories: {', '.join(sorted(all_categories))}")

    # Show top items
    print("\n" + "=" * 80)
    print("TOP 10 ITEMS (Across All Sources)")
    print("=" * 80)

    # Sort by relevance score
    all_items.sort(key=lambda x: x.relevance_score, reverse=True)

    for i, item in enumerate(all_items[:10], 1):
        print(f"\n{i}. {item.title}")
        print(
            f"   Source: {item.source} | Category: {item.category} | Score: {item.relevance_score}/10"
        )
        print(f"   URL: {item.url}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(test_multi_source())
