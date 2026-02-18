#!/usr/bin/env python3
"""
Non-interactive Telegram test - posts immediately without confirmation.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.newsletter import Newsletter, NewsletterItem
from src.publishing.telegram_publisher import TelegramPublisher
from src.utils.logger import configure_logging


async def test_telegram():
    """Test Telegram publisher - auto-post without confirmation."""

    configure_logging(log_level="INFO", pretty_console=True)

    print("=" * 60)
    print("TELEGRAM PUBLISHER - AUTO TEST")
    print("=" * 60)

    # Create test newsletter
    newsletter = Newsletter(
        date=datetime.now().strftime("%Y-%m-%d-%H"),
        items=[
            NewsletterItem(
                title="🧪 ElvAgent End-to-End Test",
                url="https://github.com/yourusername/ElvAgent",
                summary="Testing the full pipeline: ArXiv research → Content processing → Telegram publishing. This message confirms the integration is working!",
                category="research",
                source="test",
                relevance_score=10,
            ),
            NewsletterItem(
                title="✅ Multi-Platform Publishing Ready",
                url="https://example.com/test",
                summary="ElvAgent now supports Discord, Markdown, Twitter, Instagram, and Telegram. All platforms tested and operational.",
                category="product",
                source="test",
                relevance_score=9,
            ),
        ],
        summary="Testing ElvAgent's end-to-end pipeline with real Telegram posting!",
        item_count=2,
    )

    # Initialize and test
    print("\n1. Initializing Telegram publisher...")
    publisher = TelegramPublisher()

    print("2. Validating credentials...")
    if not publisher.validate_credentials():
        print("❌ Credentials missing!")
        return
    print("✅ Credentials OK")

    print("\n3. Testing bot connection...")
    try:
        me = await publisher.bot.get_me()
        print(f"✅ Connected: @{me.username}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    print("\n4. Posting to Telegram...")
    print(f"   → Chat ID: {publisher.chat_id}")

    result = await publisher.publish_newsletter(newsletter)

    print("\n" + "=" * 60)
    if result.success:
        print("✅ SUCCESS!")
        print("=" * 60)
        print(f"Message: {result.message}")
        print(f"Message IDs: {result.metadata.get('message_ids', [])}")
        print("\n🎉 Check your Telegram to see the message!")
    else:
        print("❌ FAILED!")
        print("=" * 60)
        print(f"Error: {result.error}")
    print()


if __name__ == "__main__":
    asyncio.run(test_telegram())
