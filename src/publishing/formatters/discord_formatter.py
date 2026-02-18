"""
Discord formatter for generating Discord webhook payloads.
"""

from typing import Any

from src.config.constants import PLATFORM_LIMITS
from src.models.newsletter import Newsletter
from src.publishing.formatters.base_formatter import BaseFormatter


class DiscordFormatter(BaseFormatter):
    """Format newsletters for Discord webhooks with rich embeds."""

    # Category colors (Discord hex colors as integers)
    CATEGORY_COLORS = {
        "research": 0x5865F2,  # Blue
        "product": 0x57F287,  # Green
        "funding": 0xFEE75C,  # Yellow
        "news": 0xEB459E,  # Pink
        "breakthrough": 0xED4245,  # Red
        "regulation": 0x99AAB5,  # Gray
    }

    def __init__(self):
        super().__init__("discord")
        self.max_chars = PLATFORM_LIMITS["discord"]["max_chars"]
        self.max_embeds = PLATFORM_LIMITS["discord"]["max_embeds"]

    def format(self, newsletter: Newsletter) -> dict[str, Any]:
        """
        Generate Discord webhook payload with embeds.

        Args:
            newsletter: Newsletter object to format

        Returns:
            Dictionary containing Discord webhook payload
        """
        embeds = []

        # Main embed (summary)
        main_embed = {
            "title": f"🤖 AI Newsletter - {newsletter.date}",
            "description": newsletter.summary or "Today's top AI updates",
            "color": 0x5865F2,  # Discord blurple
            "footer": {"text": f"{newsletter.item_count} items | ElvAgent"},
        }
        embeds.append(main_embed)

        # Item embeds (up to max_embeds-1 to account for main embed)
        items_to_include = min(len(newsletter.items), self.max_embeds - 1)

        for _idx, item in enumerate(newsletter.items[:items_to_include], 1):
            embed = {
                "title": self._truncate(item.title, 256),
                "url": item.url,
                "description": self._truncate(item.summary, 2048),
                "color": self._get_category_color(item.category),
                "fields": [
                    {"name": "Source", "value": item.source.title(), "inline": True},
                    {"name": "Category", "value": item.category.title(), "inline": True},
                    {"name": "Score", "value": f"{item.relevance_score}/10", "inline": True},
                ],
            }
            embeds.append(embed)

        return {
            "embeds": embeds,
            "username": "ElvAgent Newsletter",
            "avatar_url": "https://via.placeholder.com/128",  # TODO: Replace with real logo
        }

    def _get_category_color(self, category: str) -> int:
        """
        Map categories to Discord colors.

        Args:
            category: Category name

        Returns:
            Discord color as integer
        """
        return self.CATEGORY_COLORS.get(category, 0x5865F2)

    def _truncate(self, text: str, max_len: int) -> str:
        """
        Truncate text to Discord limits.

        Args:
            text: Text to truncate
            max_len: Maximum length

        Returns:
            Truncated text with ellipsis if needed
        """
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."
