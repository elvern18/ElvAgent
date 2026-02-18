#!/usr/bin/env python3
"""
Quick test script for Telegram publishing.
Tests bot authentication and message posting.
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
    """Test Telegram publisher with sample newsletter."""

    # Configure logging
    configure_logging(log_level="INFO", pretty_console=True)

    print("=" * 60)
    print("Testing Telegram Publisher")
    print("=" * 60)

    # Create test newsletter
    newsletter = Newsletter(
        date=datetime.now().strftime("%Y-%m-%d-%H"),
        items=[
            NewsletterItem(
                title="Testing ElvAgent Telegram Integration",
                url="https://github.com/yourusername/ElvAgent",
                summary="This is a test post from ElvAgent to verify Telegram Bot API integration is working correctly.",
                category="research",
                source="manual",
                relevance_score=10,
            ),
            NewsletterItem(
                title="Automated AI News Delivery",
                url="https://example.com/test",
                summary="Telegram provides a simple, free API for posting automated updates to channels and groups.",
                category="product",
                source="manual",
                relevance_score=9,
            ),
        ],
        summary="Testing ElvAgent's automated Telegram posting with markdown formatting!",
        item_count=2,
    )

    # Initialize publisher
    print("\n1. Initializing Telegram publisher...")
    publisher = TelegramPublisher()

    # Validate credentials
    print("\n2. Validating credentials...")
    if not publisher.validate_credentials():
        print("❌ ERROR: Telegram credentials not configured!")
        print("\nPlease add to .env:")
        print("TELEGRAM_BOT_TOKEN=your_bot_token")
        print("TELEGRAM_CHAT_ID=your_chat_id")
        print("\nQuick setup:")
        print("1. Message @BotFather on Telegram")
        print("2. Send: /newbot")
        print("3. Follow prompts to get your bot token")
        print("4. Start a chat with your bot")
        print("5. Get your chat ID from @userinfobot")
        return

    print("✅ Credentials found")

    # Test bot connection
    print("\n3. Testing bot connection...")
    try:
        me = await publisher.bot.get_me()
        print(f"✅ Bot connected: @{me.username}")
    except Exception as e:
        print(f"❌ Bot connection failed: {e}")
        print("\nCheck your TELEGRAM_BOT_TOKEN is correct.")
        return

    # Format content
    print("\n4. Formatting newsletter as Telegram message...")
    messages = await publisher.format_content(newsletter)

    print(f"\n📝 Generated {len(messages)} message(s):")
    for i, message in enumerate(messages, 1):
        print(f"\n--- Message {i} ({len(message)} chars) ---")
        # Show first 500 chars
        preview = message if len(message) <= 500 else message[:497] + "..."
        print(preview)
        if len(message) > 500:
            print(f"\n... (total {len(message)} chars)")

    # Ask for confirmation
    print("\n" + "=" * 60)
    print("⚠️  READY TO POST TO TELEGRAM")
    print("=" * 60)
    print(f"This will send {len(messages)} message(s) to chat ID: {publisher.chat_id}")
    response = input("\nPost to Telegram? (yes/no): ")

    if response.lower() != "yes":
        print("\n❌ Aborted. No messages sent.")
        return

    # Publish
    print("\n5. Posting to Telegram...")
    result = await publisher.publish_newsletter(newsletter)

    print("\n" + "=" * 60)
    if result.success:
        print("✅ SUCCESS!")
        print("=" * 60)
        print(f"Posted: {result.message}")
        print(f"Message IDs: {result.metadata.get('message_ids', [])}")
        print("\nCheck your Telegram chat/channel to see the message!")
    else:
        print("❌ FAILED!")
        print("=" * 60)
        print(f"Error: {result.error}")
        print("\nCommon issues:")
        print("  - Bot token invalid (check TELEGRAM_BOT_TOKEN)")
        print("  - Chat ID wrong (make sure bot is in the chat/channel)")
        print("  - Bot doesn't have permission to post in channel")

    print("\n")


if __name__ == "__main__":
    asyncio.run(test_telegram())
