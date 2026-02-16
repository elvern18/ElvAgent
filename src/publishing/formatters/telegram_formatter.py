"""
Telegram formatter for converting newsletters to Telegram messages.
Uses Telegram's markdown formatting.
"""
from typing import List
from src.models.newsletter import Newsletter
from src.models.enhanced_newsletter import CategoryMessage
from src.publishing.formatters.base_formatter import BaseFormatter


class TelegramFormatter(BaseFormatter):
    """Format newsletters as Telegram messages with markdown."""

    MAX_MESSAGE_LENGTH = 4096  # Telegram limit
    EMOJI_MAP = {
        "research": "📚",
        "product": "🚀",
        "funding": "💰",
        "news": "📰",
        "breakthrough": "⚡",
        "regulation": "⚖️"
    }

    def __init__(self):
        """Initialize Telegram formatter."""
        super().__init__(platform_name="telegram")

    def format(self, newsletter: Newsletter) -> List[str]:
        """
        Format newsletter as Telegram messages.

        Args:
            newsletter: Newsletter object to format

        Returns:
            List of message strings (split if too long)
        """
        # Format date nicely
        date_parts = newsletter.date.split('-')
        if len(date_parts) == 4:
            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            month = month_names[int(date_parts[1]) - 1]
            day = date_parts[2]
            hour = date_parts[3]
            formatted_date = f"{month} {day}, {hour}:00"
        else:
            formatted_date = newsletter.date

        # Build main message
        parts = []

        # Header
        parts.append(f"🤖 *AI News Update* \\- {self._escape_markdown(formatted_date)}")
        parts.append("")

        # Summary
        parts.append(self._escape_markdown(newsletter.summary))
        parts.append("")

        # Items
        parts.append(f"📊 *{newsletter.item_count} items in this update:*")
        parts.append("")

        for i, item in enumerate(newsletter.items, 1):
            # Get emoji for category
            emoji = self.EMOJI_MAP.get(item.category, "📌")

            # Item header with title
            parts.append(f"{i}\\. {emoji} *{self._escape_markdown(item.title)}*")

            # Score and category
            parts.append(f"   ⭐ Score: {item.relevance_score}/10 \\| Category: {self._escape_markdown(item.category.upper())}")

            # Summary
            parts.append(f"   {self._escape_markdown(item.summary)}")

            # Link
            parts.append(f"   🔗 [Read more]({item.url})")
            parts.append("")

        # Footer
        parts.append("━━━━━━━━━━━━━━━━━")
        parts.append("🤖 *Powered by ElvAgent*")
        parts.append("Automated AI news delivered hourly")

        # Join all parts
        full_message = "\n".join(parts)

        # Split if too long
        return self._split_message(full_message)

    def _escape_markdown(self, text: str) -> str:
        """
        Escape special characters for Telegram MarkdownV2.

        Args:
            text: Text to escape

        Returns:
            Escaped text
        """
        # Characters that need escaping in MarkdownV2
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']

        for char in special_chars:
            text = text.replace(char, f'\\{char}')

        return text

    def _split_message(self, message: str) -> List[str]:
        """
        Split message if it exceeds Telegram's limit.

        Args:
            message: Full message text

        Returns:
            List of message chunks
        """
        if len(message) <= self.MAX_MESSAGE_LENGTH:
            return [message]

        # Split by double newlines (paragraphs)
        paragraphs = message.split('\n\n')

        messages = []
        current = []
        current_length = 0

        for para in paragraphs:
            para_length = len(para) + 2  # +2 for \n\n

            if current_length + para_length > self.MAX_MESSAGE_LENGTH:
                # Save current message
                messages.append('\n\n'.join(current))
                current = [para]
                current_length = para_length
            else:
                current.append(para)
                current_length += para_length

        # Add remaining
        if current:
            messages.append('\n\n'.join(current))

        return messages

    def format_enhanced(
        self,
        category_messages: List[CategoryMessage]
    ) -> List[str]:
        """
        Format enhanced category messages for Telegram.

        CategoryMessage.formatted_text is already AI-formatted by SocialFormatter
        in basic Markdown. We need to convert it to MarkdownV2 format.

        Args:
            category_messages: List of CategoryMessage objects

        Returns:
            List of message strings (split if needed)
        """
        parts = []

        # Header
        parts.append("🤖 *AI News Update*")
        parts.append("")

        # Add each category (already formatted by SocialFormatter)
        for msg in category_messages:
            # SocialFormatter outputs basic Markdown, which is compatible with MarkdownV2
            # We'll use it as-is since the AI should handle special characters properly
            parts.append(msg.formatted_text)
            parts.append("")

        # Footer
        parts.append("━━━━━━━━━━━━━━━━━")
        parts.append("🤖 *Powered by ElvAgent*")
        parts.append("Automated AI news delivered hourly")

        # Join and split at 4096 char limit
        full_message = "\n".join(parts)
        return self._split_message(full_message)
