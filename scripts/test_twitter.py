#!/usr/bin/env python3
"""
Quick test script for Twitter publishing.
Tests authentication and basic tweet posting.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime

from src.models.newsletter import Newsletter, NewsletterItem
from src.publishing.twitter_publisher import TwitterPublisher
from src.utils.logger import configure_logging


async def test_twitter():
    """Test Twitter publisher with sample newsletter."""

    # Configure logging
    configure_logging(log_level="INFO", pretty_console=True)

    print("=" * 60)
    print("Testing Twitter Publisher")
    print("=" * 60)

    # Create test newsletter
    newsletter = Newsletter(
        date=datetime.now().strftime("%Y-%m-%d-%H"),
        items=[
            NewsletterItem(
                title="Testing ElvAgent Twitter Integration",
                url="https://github.com/yourusername/ElvAgent",
                summary="This is a test post from ElvAgent to verify Twitter API integration is working correctly.",
                category="test",
                source="manual",
                relevance_score=10,
            ),
            NewsletterItem(
                title="Second Test Item",
                url="https://example.com/test",
                summary="Testing multi-tweet thread functionality with a second item.",
                category="test",
                source="manual",
                relevance_score=9,
            ),
        ],
        summary="Testing ElvAgent's automated Twitter posting. This is a test thread!",
        item_count=2,
    )

    # Initialize publisher
    print("\n1. Initializing Twitter publisher...")
    publisher = TwitterPublisher()

    # Validate credentials
    print("\n2. Validating credentials...")
    if not publisher.validate_credentials():
        print("❌ ERROR: Twitter credentials not configured!")
        print("\nPlease add to .env:")
        print("TWITTER_API_KEY=your_key")
        print("TWITTER_API_SECRET=your_secret")
        print("TWITTER_ACCESS_TOKEN=your_token")
        print("TWITTER_ACCESS_SECRET=your_token_secret")
        return

    print("✅ Credentials found")

    # Format content
    print("\n3. Formatting newsletter as Twitter thread...")
    tweets = await publisher.format_content(newsletter)

    print(f"\n📝 Generated {len(tweets)} tweets:")
    for i, tweet in enumerate(tweets, 1):
        print(f"\n--- Tweet {i} ({len(tweet)} chars) ---")
        print(tweet)

    # Ask for confirmation
    print("\n" + "=" * 60)
    print("⚠️  READY TO POST TO TWITTER")
    print("=" * 60)
    response = input("\nPost this thread to Twitter? (yes/no): ")

    if response.lower() != "yes":
        print("\n❌ Aborted. No tweets posted.")
        return

    # Publish
    print("\n4. Posting to Twitter...")
    result = await publisher.publish_newsletter(newsletter)

    print("\n" + "=" * 60)
    if result.success:
        print("✅ SUCCESS!")
        print("=" * 60)
        print(f"Posted: {result.message}")
        if result.metadata and "thread_url" in result.metadata:
            print(f"Thread URL: {result.metadata['thread_url']}")
            print(f"Tweet IDs: {result.metadata.get('tweet_ids', [])}")
    else:
        print("❌ FAILED!")
        print("=" * 60)
        print(f"Error: {result.error}")

    print("\n")


if __name__ == "__main__":
    asyncio.run(test_twitter())
