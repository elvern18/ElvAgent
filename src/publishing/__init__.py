"""
Publishing module for distributing newsletters to multiple platforms.
"""

from src.publishing.base import BasePublisher, PublishResult
from src.publishing.discord_publisher import DiscordPublisher
from src.publishing.instagram_publisher import InstagramPublisher
from src.publishing.markdown_publisher import MarkdownPublisher
from src.publishing.telegram_publisher import TelegramPublisher
from src.publishing.twitter_publisher import TwitterPublisher

__all__ = [
    "BasePublisher",
    "PublishResult",
    "MarkdownPublisher",
    "DiscordPublisher",
    "TwitterPublisher",
    "InstagramPublisher",
    "TelegramPublisher",
]
