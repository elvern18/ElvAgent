"""
Test script for TechCrunch researcher.
Fetches and displays recent AI news from TechCrunch.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.research.techcrunch_researcher import TechCrunchResearcher


async def test_techcrunch():
    """Test TechCrunch researcher."""
    print("=" * 80)
    print("Testing TechCrunch Researcher")
    print("=" * 80)

    researcher = TechCrunchResearcher(max_items=5)

    try:
        items = await researcher.research()

        print(f"\n✅ Found {len(items)} relevant articles\n")

        for i, item in enumerate(items, 1):
            print(f"{i}. {item.title}")
            print(f"   URL: {item.url}")
            print(f"   Score: {item.relevance_score}/10")
            print(f"   Category: {item.category}")
            print(f"   Summary: {item.summary[:150]}...")
            print()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_techcrunch())
