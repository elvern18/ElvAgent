"""
Image generator for creating newsletter cards.
Generates clean, readable images with text overlays using Pillow.
"""

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


class NewsletterImageGenerator:
    """Generate newsletter card images with text overlays."""

    # Design constants
    IMAGE_WIDTH = 1080  # Instagram optimal width
    IMAGE_HEIGHT = 1080  # Square format
    BACKGROUND_COLOR = (255, 255, 255)  # White
    TEXT_COLOR = (30, 30, 30)  # Dark gray
    ACCENT_COLOR = (88, 101, 242)  # Blue (matches Discord brand)
    HEADER_COLOR = (88, 101, 242)  # Blue header

    MARGIN = 80
    HEADER_HEIGHT = 200

    # Category colors
    CATEGORY_COLORS = {
        "research": (88, 101, 242),  # Blue
        "product": (87, 242, 135),  # Green
        "funding": (254, 231, 92),  # Yellow
        "news": (235, 69, 158),  # Pink
        "breakthrough": (237, 66, 69),  # Red
        "regulation": (153, 170, 181),  # Gray
    }

    def __init__(self, output_dir: Path | None = None):
        """
        Initialize image generator.

        Args:
            output_dir: Directory to save generated images
        """
        self.output_dir = output_dir or Path("data/images/newsletter_cards")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Try to load fonts (fallback to default if not available)
        try:
            self.title_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48
            )
            self.body_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36
            )
            self.small_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28
            )
            self.header_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56
            )
        except Exception:
            # Fallback to default font
            self.title_font = ImageFont.load_default()
            self.body_font = ImageFont.load_default()
            self.small_font = ImageFont.load_default()
            self.header_font = ImageFont.load_default()

    def create_intro_card(self, date: str, summary: str, item_count: int) -> Path:
        """
        Create intro card with newsletter summary.

        Args:
            date: Newsletter date (e.g., "Feb 16, 2026")
            summary: Newsletter summary text
            item_count: Number of items in newsletter

        Returns:
            Path to generated image
        """
        img = Image.new("RGB", (self.IMAGE_WIDTH, self.IMAGE_HEIGHT), self.BACKGROUND_COLOR)
        draw = ImageDraw.Draw(img)

        y = self.MARGIN

        # Header background
        draw.rectangle([(0, 0), (self.IMAGE_WIDTH, self.HEADER_HEIGHT)], fill=self.HEADER_COLOR)

        # Title
        title_text = "🤖 AI News Update"
        draw.text((self.MARGIN, y + 30), title_text, fill=(255, 255, 255), font=self.header_font)

        # Date
        date_text = date
        draw.text((self.MARGIN, y + 110), date_text, fill=(255, 255, 255), font=self.body_font)

        # Summary (wrapped)
        y = self.HEADER_HEIGHT + 80
        wrapped_summary = textwrap.fill(summary, width=35)
        draw.text((self.MARGIN, y), wrapped_summary, fill=self.TEXT_COLOR, font=self.body_font)

        # Item count
        y = self.IMAGE_HEIGHT - self.MARGIN - 60
        count_text = f"📊 {item_count} items in this update"
        draw.text((self.MARGIN, y), count_text, fill=self.ACCENT_COLOR, font=self.small_font)

        # Swipe hint
        swipe_text = "👉 Swipe to see all →"
        draw.text((self.MARGIN, y + 40), swipe_text, fill=self.TEXT_COLOR, font=self.small_font)

        # Save
        filepath = self.output_dir / "intro.jpg"
        img.save(filepath, quality=95)
        return filepath

    def create_item_card(
        self, title: str, summary: str, category: str, score: int, index: int
    ) -> Path:
        """
        Create card for a single newsletter item.

        Args:
            title: Item title
            summary: Item summary
            category: Content category
            score: Relevance score (1-10)
            index: Item number (1-based)

        Returns:
            Path to generated image
        """
        img = Image.new("RGB", (self.IMAGE_WIDTH, self.IMAGE_HEIGHT), self.BACKGROUND_COLOR)
        draw = ImageDraw.Draw(img)

        # Get category color
        category_color = self.CATEGORY_COLORS.get(category.lower(), self.ACCENT_COLOR)

        y = self.MARGIN

        # Item number circle
        circle_radius = 40
        circle_center = (self.MARGIN + circle_radius, y + circle_radius)
        draw.ellipse(
            [
                (circle_center[0] - circle_radius, circle_center[1] - circle_radius),
                (circle_center[0] + circle_radius, circle_center[1] + circle_radius),
            ],
            fill=category_color,
        )
        # Draw number
        number_text = str(index)
        # Get text bbox to center it
        bbox = draw.textbbox((0, 0), number_text, font=self.header_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        draw.text(
            (circle_center[0] - text_width // 2, circle_center[1] - text_height // 2 - 5),
            number_text,
            fill=(255, 255, 255),
            font=self.header_font,
        )

        # Category badge
        y += 20
        category_text = f"📚 {category.upper()}"
        draw.text((self.MARGIN + 120, y), category_text, fill=category_color, font=self.small_font)

        # Score
        score_text = f"⭐ {score}/10"
        draw.text(
            (self.IMAGE_WIDTH - self.MARGIN - 150, y),
            score_text,
            fill=self.TEXT_COLOR,
            font=self.small_font,
        )

        # Title (wrapped, bold)
        y += 80
        wrapped_title = textwrap.fill(title, width=30)
        draw.text((self.MARGIN, y), wrapped_title, fill=self.TEXT_COLOR, font=self.title_font)

        # Calculate title height to position summary
        title_lines = len(wrapped_title.split("\n"))
        y += title_lines * 60 + 40

        # Separator line
        draw.line(
            [(self.MARGIN, y), (self.IMAGE_WIDTH - self.MARGIN, y)], fill=category_color, width=3
        )
        y += 40

        # Summary (wrapped)
        wrapped_summary = textwrap.fill(summary, width=35)
        # Limit to 8 lines
        summary_lines = wrapped_summary.split("\n")[:8]
        if len(summary_lines) < len(wrapped_summary.split("\n")):
            summary_lines[-1] = summary_lines[-1][:50] + "..."
        wrapped_summary = "\n".join(summary_lines)

        draw.text((self.MARGIN, y), wrapped_summary, fill=self.TEXT_COLOR, font=self.body_font)

        # Footer hint
        y = self.IMAGE_HEIGHT - self.MARGIN - 40
        footer_text = "🔗 Link in caption"
        draw.text((self.MARGIN, y), footer_text, fill=self.ACCENT_COLOR, font=self.small_font)

        # Save
        filepath = self.output_dir / f"item_{index}.jpg"
        img.save(filepath, quality=95)
        return filepath

    def create_outro_card(self) -> Path:
        """
        Create outro card with call-to-action.

        Returns:
            Path to generated image
        """
        img = Image.new("RGB", (self.IMAGE_WIDTH, self.IMAGE_HEIGHT), self.BACKGROUND_COLOR)
        draw = ImageDraw.Draw(img)

        # Background gradient effect (simple colored bars)
        bar_height = self.IMAGE_HEIGHT // 5
        colors = [(88, 101, 242), (87, 242, 135), (254, 231, 92), (235, 69, 158), (237, 66, 69)]
        for i, color in enumerate(colors):
            draw.rectangle(
                [(0, i * bar_height), (self.IMAGE_WIDTH, (i + 1) * bar_height)], fill=color
            )

        # Semi-transparent overlay
        overlay = Image.new("RGBA", (self.IMAGE_WIDTH, self.IMAGE_HEIGHT), (255, 255, 255, 200))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        # Center content
        y = self.IMAGE_HEIGHT // 2 - 150

        # Main text
        text1 = "That's all for now!"
        bbox = draw.textbbox((0, 0), text1, font=self.header_font)
        text_width = bbox[2] - bbox[0]
        draw.text(
            ((self.IMAGE_WIDTH - text_width) // 2, y),
            text1,
            fill=self.TEXT_COLOR,
            font=self.header_font,
        )

        y += 100
        text2 = "Follow for hourly AI updates"
        bbox = draw.textbbox((0, 0), text2, font=self.body_font)
        text_width = bbox[2] - bbox[0]
        draw.text(
            ((self.IMAGE_WIDTH - text_width) // 2, y),
            text2,
            fill=self.TEXT_COLOR,
            font=self.body_font,
        )

        y += 80
        text3 = "🤖 Powered by ElvAgent"
        bbox = draw.textbbox((0, 0), text3, font=self.body_font)
        text_width = bbox[2] - bbox[0]
        draw.text(
            ((self.IMAGE_WIDTH - text_width) // 2, y),
            text3,
            fill=self.ACCENT_COLOR,
            font=self.body_font,
        )

        # Save
        filepath = self.output_dir / "outro.jpg"
        img.save(filepath, quality=95)
        return filepath
