"""
Instagram formatter for converting newsletters to carousel posts.
Generates images with text overlays and formatted captions.
"""

from pathlib import Path

from src.models.newsletter import Newsletter
from src.publishing.formatters.base_formatter import BaseFormatter
from src.publishing.image_generator import NewsletterImageGenerator


class InstagramFormatter(BaseFormatter):
    """Format newsletters as Instagram carousel posts with images."""

    MAX_CAPTION_LENGTH = 2200
    MAX_CAROUSEL_ITEMS = 10

    def __init__(self):
        """Initialize Instagram formatter."""
        super().__init__(platform_name="instagram")
        self.image_generator = NewsletterImageGenerator()

    def format(self, newsletter: Newsletter) -> tuple[list[Path], str]:
        """
        Format newsletter as Instagram carousel post.

        Args:
            newsletter: Newsletter object to format

        Returns:
            Tuple of (list of image paths, caption text)
        """
        images = []

        # Format date nicely (2026-02-16-10 -> Feb 16, 2026)
        date_parts = newsletter.date.split("-")
        if len(date_parts) == 4:
            month_names = [
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ]
            month = month_names[int(date_parts[1]) - 1]
            day = date_parts[2]
            year = date_parts[0]
            formatted_date = f"{month} {day}, {year}"
        else:
            formatted_date = newsletter.date

        # Image 1: Intro card
        intro_image = self.image_generator.create_intro_card(
            date=formatted_date, summary=newsletter.summary, item_count=newsletter.item_count
        )
        images.append(intro_image)

        # Images 2-N: Item cards (max 8 to leave room for outro)
        max_items = min(len(newsletter.items), self.MAX_CAROUSEL_ITEMS - 2)
        for i, item in enumerate(newsletter.items[:max_items], 1):
            item_image = self.image_generator.create_item_card(
                title=item.title,
                summary=item.summary,
                category=item.category,
                score=item.relevance_score,
                index=i,
            )
            images.append(item_image)

        # Last image: Outro card
        outro_image = self.image_generator.create_outro_card()
        images.append(outro_image)

        # Generate caption
        caption = self._format_caption(newsletter, formatted_date)

        return images, caption

    def _format_caption(self, newsletter: Newsletter, formatted_date: str) -> str:
        """
        Format caption text for Instagram post.

        Args:
            newsletter: Newsletter object
            formatted_date: Formatted date string

        Returns:
            Caption text (max 2200 chars)
        """
        # Header
        caption_parts = [
            f"🤖 AI News Update - {formatted_date}",
            "",
            f"{newsletter.summary}",
            "",
            "📊 Today's highlights:",
        ]

        # Add item titles with numbers
        for i, item in enumerate(newsletter.items, 1):
            # Truncate title if too long
            title = item.title
            if len(title) > 60:
                title = title[:57] + "..."

            caption_parts.append(f"{i}️⃣ {title}")

        caption_parts.append("")

        # Add links section
        caption_parts.append("🔗 Links:")
        for i, item in enumerate(newsletter.items, 1):
            caption_parts.append(f"{i}. {item.url}")

        caption_parts.append("")

        # Add hashtags
        hashtags = self._generate_hashtags(newsletter)
        caption_parts.append(hashtags)

        # Add footer
        caption_parts.append("")
        caption_parts.append("🤖 Powered by ElvAgent")
        caption_parts.append("Follow for hourly AI updates!")

        # Join and truncate if needed
        caption = "\n".join(caption_parts)

        if len(caption) > self.MAX_CAPTION_LENGTH:
            # Truncate and add ellipsis
            caption = caption[: self.MAX_CAPTION_LENGTH - 20] + "\n\n... See more ⬆️"

        return caption

    def _generate_hashtags(self, newsletter: Newsletter) -> str:
        """
        Generate relevant hashtags based on newsletter content.

        Args:
            newsletter: Newsletter object

        Returns:
            Hashtag string
        """
        # Base hashtags
        hashtags = ["#AI", "#MachineLearning", "#ArtificialIntelligence"]

        # Category-based hashtags
        categories = {item.category for item in newsletter.items}
        category_hashtags = {
            "research": ["#AIResearch", "#MLResearch", "#DeepLearning"],
            "product": ["#AIProducts", "#TechNews", "#Innovation"],
            "funding": ["#AIFunding", "#Startups", "#VentureCapital"],
            "news": ["#TechNews", "#AINews"],
            "breakthrough": ["#AIBreakthrough", "#TechBreakthrough"],
            "regulation": ["#AIEthics", "#TechPolicy"],
        }

        for category in categories:
            if category in category_hashtags:
                hashtags.extend(category_hashtags[category][:2])

        # Add general tech hashtags
        hashtags.extend(["#Technology", "#Future", "#Automation"])

        # Limit to 15 hashtags (Instagram best practice)
        hashtags = hashtags[:15]

        return " ".join(hashtags)
