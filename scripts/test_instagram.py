#!/usr/bin/env python3
"""
Quick test script for Instagram publishing.
Tests authentication and carousel post creation.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.newsletter import Newsletter, NewsletterItem
from src.publishing.instagram_publisher import InstagramPublisher
from src.utils.logger import configure_logging


async def test_instagram():
    """Test Instagram publisher with sample newsletter."""

    # Configure logging
    configure_logging(log_level="INFO", pretty_console=True)

    print("=" * 60)
    print("Testing Instagram Publisher")
    print("=" * 60)

    # Create test newsletter
    newsletter = Newsletter(
        date=datetime.now().strftime("%Y-%m-%d-%H"),
        items=[
            NewsletterItem(
                title="Testing ElvAgent Instagram Integration",
                url="https://github.com/yourusername/ElvAgent",
                summary="This is a test post from ElvAgent to verify Instagram Graph API integration is working correctly with carousel posts and text-on-image approach.",
                category="research",
                source="manual",
                relevance_score=10,
            ),
            NewsletterItem(
                title="AI-Generated Newsletter Cards",
                url="https://example.com/test",
                summary="Testing automated image generation with Pillow. Each newsletter item gets a beautifully formatted card with category colors, scores, and clean typography.",
                category="product",
                source="manual",
                relevance_score=9,
            ),
            NewsletterItem(
                title="Carousel Post Functionality",
                url="https://example.com/carousel",
                summary="Instagram carousel posts allow up to 10 images per post, perfect for multi-item newsletters. Users can swipe through all the day's AI highlights.",
                category="news",
                source="manual",
                relevance_score=8,
            ),
        ],
        summary="Testing ElvAgent's automated Instagram posting with text-on-image carousel posts!",
        item_count=3,
    )

    # Initialize publisher
    print("\n1. Initializing Instagram publisher...")
    publisher = InstagramPublisher()

    # Validate credentials
    print("\n2. Validating credentials...")
    if not publisher.validate_credentials():
        print("❌ ERROR: Instagram credentials not configured!")
        print("\nPlease add to .env:")
        print("INSTAGRAM_ACCESS_TOKEN=your_access_token")
        print("INSTAGRAM_BUSINESS_ACCOUNT_ID=your_business_account_id")
        print("\nSee setup instructions in the documentation.")
        return

    print("✅ Credentials found")

    # Format content
    print("\n3. Generating images and formatting caption...")
    image_paths, caption = await publisher.format_content(newsletter)

    print(f"\n📸 Generated {len(image_paths)} images:")
    for i, path in enumerate(image_paths, 1):
        print(f"  {i}. {path}")

    print(f"\n📝 Caption ({len(caption)} chars):")
    print("-" * 60)
    # Show first 500 chars of caption
    preview = caption if len(caption) <= 500 else caption[:497] + "..."
    print(preview)
    if len(caption) > 500:
        print(f"\n... (total {len(caption)} chars)")
    print("-" * 60)

    # Ask for confirmation
    print("\n" + "=" * 60)
    print("⚠️  READY TO POST TO INSTAGRAM")
    print("=" * 60)
    print(f"This will create a carousel post with {len(image_paths)} images.")
    print("The post will appear on your Instagram Business account.")
    response = input("\nPost this carousel to Instagram? (yes/no): ")

    if response.lower() != "yes":
        print("\n❌ Aborted. No post created.")
        print(f"\n📁 Images saved to: {image_paths[0].parent}")
        print("You can view the generated images there.")
        return

    # Publish
    print("\n4. Posting to Instagram...")
    result = await publisher.publish_newsletter(newsletter)

    print("\n" + "=" * 60)
    if result.success:
        print("✅ SUCCESS!")
        print("=" * 60)
        print(f"Posted: {result.message}")
        if result.metadata and "post_url" in result.metadata:
            print(f"Post URL: {result.metadata['post_url']}")
            print(f"Post ID: {result.metadata.get('post_id', 'N/A')}")
    else:
        print("❌ FAILED!")
        print("=" * 60)
        print(f"Error: {result.error}")
        print("\nCommon issues:")
        print("  - Access token expired (regenerate in Facebook Developer Console)")
        print("  - App not approved (apply for Instagram Content Publishing permission)")
        print("  - Business account not properly linked to Facebook Page")

    print("\n")


if __name__ == "__main__":
    asyncio.run(test_instagram())
