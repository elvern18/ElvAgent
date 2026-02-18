#!/usr/bin/env python3
"""
Manual test script for publishers.
Tests both Markdown and Discord publishers with sample data.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.newsletter import Newsletter, NewsletterItem
from src.publishing.discord_publisher import DiscordPublisher
from src.publishing.markdown_publisher import MarkdownPublisher


async def test_markdown_publisher():
    """Test Markdown publisher with sample newsletter."""
    print("\n" + "=" * 60)
    print("Testing Markdown Publisher")
    print("=" * 60)

    # Create sample newsletter
    items = [
        NewsletterItem(
            title="Novel LLM Architecture Improves Reasoning",
            url="https://arxiv.org/abs/2024.12345",
            summary="Researchers from MIT propose a new transformer architecture that achieves state-of-the-art results on reasoning benchmarks. The model uses a hierarchical attention mechanism that reduces computational complexity.",
            category="research",
            source="arxiv",
            relevance_score=9,
            metadata={"authors": ["John Doe", "Jane Smith"], "citations": 0},
        ),
        NewsletterItem(
            title="OpenAI Releases GPT-5 with Multimodal Capabilities",
            url="https://openai.com/blog/gpt5",
            summary="OpenAI announces GPT-5, featuring native multimodal understanding, improved reasoning, and 10x faster inference. The model can now process video, audio, and text simultaneously.",
            category="product",
            source="openai",
            relevance_score=10,
        ),
        NewsletterItem(
            title="Anthropic Raises $500M Series C",
            url="https://techcrunch.com/2026/02/15/anthropic-funding",
            summary="AI safety company Anthropic raises $500M in Series C funding led by Google Ventures. The funding will support research into constitutional AI and scaling laws.",
            category="funding",
            source="techcrunch",
            relevance_score=8,
            metadata={"amount": "$500M", "lead_investor": "Google Ventures"},
        ),
    ]

    newsletter = Newsletter(
        date="2026-02-15-14",
        items=items,
        summary="Major developments in AI this hour: breakthrough in reasoning architecture, GPT-5 launch, and significant funding for AI safety research.",
        item_count=3,
    )

    # Test publisher
    publisher = MarkdownPublisher()
    result = await publisher.publish_newsletter(newsletter)

    # Display results
    print(f"\nStatus: {'✅ SUCCESS' if result.success else '❌ FAILED'}")
    print(f"Platform: {result.platform}")
    print(f"Message: {result.message}")

    if result.metadata:
        print("\nMetadata:")
        for key, value in result.metadata.items():
            print(f"  {key}: {value}")

    if result.success:
        filepath = result.metadata.get("filepath")
        if filepath and Path(filepath).exists():
            print("\n📄 File created successfully!")
            print("\nPreview (first 500 chars):")
            print("-" * 60)
            content = Path(filepath).read_text()
            print(content[:500])
            print("...")


async def test_discord_publisher():
    """Test Discord publisher (requires webhook URL in .env)."""
    print("\n" + "=" * 60)
    print("Testing Discord Publisher")
    print("=" * 60)

    # Create sample newsletter
    items = [
        NewsletterItem(
            title="Breakthrough in Quantum Machine Learning",
            url="https://arxiv.org/abs/2024.99999",
            summary="Scientists demonstrate quantum advantage in neural network training, achieving 100x speedup on specific tasks.",
            category="breakthrough",
            source="arxiv",
            relevance_score=10,
        ),
        NewsletterItem(
            title="New AI Regulation Proposed in EU",
            url="https://ec.europa.eu/ai-act-2026",
            summary="European Commission proposes updated AI Act with stricter requirements for foundation models and generative AI systems.",
            category="regulation",
            source="eu",
            relevance_score=7,
        ),
    ]

    newsletter = Newsletter(
        date="2026-02-15-14",
        items=items,
        summary="Critical updates: quantum ML breakthrough and new EU AI regulations.",
        item_count=2,
    )

    # Test publisher
    publisher = DiscordPublisher()

    # Check credentials first
    if not publisher.validate_credentials():
        print("\n⚠️  WARNING: Discord webhook URL not configured")
        print("Set DISCORD_WEBHOOK_URL in .env to test Discord publishing")
        print("\nSkipping Discord test...")
        return

    result = await publisher.publish_newsletter(newsletter)

    # Display results
    print(f"\nStatus: {'✅ SUCCESS' if result.success else '❌ FAILED'}")
    print(f"Platform: {result.platform}")
    print(f"Message: {result.message}")

    if result.error:
        print(f"Error: {result.error}")

    if result.metadata:
        print("\nMetadata:")
        for key, value in result.metadata.items():
            print(f"  {key}: {value}")

    if result.success:
        print("\n✨ Message posted to Discord successfully!")
        print("Check your Discord channel to see the newsletter.")


async def main():
    """Run all publisher tests."""
    print("\n🧪 Publisher Manual Test Suite")
    print("=" * 60)

    # Test Markdown (always works)
    await test_markdown_publisher()

    # Test Discord (requires webhook)
    await test_discord_publisher()

    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
