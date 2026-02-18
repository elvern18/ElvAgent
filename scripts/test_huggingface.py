"""
Test script for HuggingFace researcher.
Fetches and displays recent papers from HuggingFace daily papers.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.research.huggingface_researcher import HuggingFaceResearcher


async def test_huggingface():
    """Test HuggingFace researcher."""
    print("=" * 80)
    print("Testing HuggingFace Researcher")
    print("=" * 80)

    researcher = HuggingFaceResearcher(max_items=5)

    try:
        # Also test fetch_content directly to see raw items
        print("\nFetching raw content...")
        raw_items = await researcher.fetch_content()
        print(f"Raw items (before sorting): {len(raw_items)}")

        items = await researcher.research()

        print(f"\n✅ Found {len(items)} relevant papers (after scoring and sorting)\n")

        for i, item in enumerate(items, 1):
            print(f"{i}. {item.title}")
            print(f"   URL: {item.url}")
            print(f"   Score: {item.relevance_score}/10")
            print(f"   Category: {item.category}")
            print(f"   Comments: {item.metadata.get('num_comments', 0)}")
            print(f"   Summary: {item.summary[:150]}...")
            print()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_huggingface())
