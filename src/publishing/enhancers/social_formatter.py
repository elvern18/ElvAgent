"""
AI-powered social media message formatting.
Creates visually appealing Telegram messages with proper hierarchy.
"""
from anthropic import AsyncAnthropic
import json
from typing import List
from src.config.settings import settings
from src.models.enhanced_newsletter import EnhancedNewsletterItem, CategoryMessage
from src.utils.logger import get_logger

logger = get_logger("enhancer.formatter")


class SocialFormatter:
    """
    Format category messages using Claude Haiku.

    Creates visually appealing Telegram messages with proper
    spacing, emojis, and hierarchy optimized for mobile reading.
    """

    SYSTEM_PROMPT = """You format content for Telegram with perfect visual hierarchy.
Your messages are scannable, engaging, and optimized for mobile reading."""

    USER_PROMPT_TEMPLATE = """Format this category for Telegram:

Category: {category}
Title: {title}
Date: {date}
Items: {items_json}

Requirements:
1. Start with category title (bold)
2. Add intro line if needed
3. Number each item (1-5)
4. For each item:
   - Viral headline (bold)
   - Takeaway on new line
   - Engagement metrics (if available)
   - Link with "🔗 Read more"
5. Use proper spacing between items
6. Markdown formatting (bold with *, links with [text](url))
7. Professional but engaging tone
8. End with separator line: ━━━━━━━━━━━━━━━━

Example format:

**{title}**

Top stories today:

1. **🔬 AI Achieves 10x Better Image Understanding**
   💡 Why it matters: Makes SOTA models accessible to small teams
   ☕ 5-min read · 234 comments
   🔗 [Read more](url)

2. **💰 Startup Raises $45M to Challenge OpenAI**
   💡 Why it matters: Could accelerate competition in foundation models
   ☕ 3-min read
   🔗 [Read more](url)

[continue for all items...]

━━━━━━━━━━━━━━━━

Return ONLY the formatted Telegram message. Use Markdown syntax. Keep it scannable and mobile-friendly."""

    def __init__(self):
        """Initialize formatter with Anthropic client."""
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-haiku-4-5-20251001"

    async def format_category(
        self,
        category: str,
        title: str,
        items: List[EnhancedNewsletterItem],
        date: str,
        timeout: int = 30
    ) -> tuple[str, float]:
        """
        Format category message using AI.

        Args:
            category: Category name
            title: Category title
            items: List of enhanced items
            date: Newsletter date
            timeout: API timeout

        Returns:
            Tuple of (formatted_text, cost_in_dollars)

        Raises:
            Exception: If API call fails
        """
        # Prepare items as JSON for prompt
        items_data = []
        for idx, item in enumerate(items, 1):
            item_dict = {
                "number": idx,
                "headline": item.viral_headline,
                "takeaway": item.takeaway,
                "url": item.url,
                "metrics": item.engagement_metrics
            }
            items_data.append(item_dict)

        # Format prompt
        prompt = self.USER_PROMPT_TEMPLATE.format(
            category=category,
            title=title,
            date=date,
            items_json=json.dumps(items_data, indent=2)
        )

        logger.debug(
            "formatting_category",
            category=category,
            item_count=len(items)
        )

        try:
            # Call Claude API
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=self.SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                timeout=timeout
            )

            # Extract formatted text
            formatted_text = response.content[0].text.strip()

            # Calculate cost
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = (input_tokens * 0.00025 / 1000) + (output_tokens * 0.00125 / 1000)

            logger.debug(
                "category_formatted",
                category=category,
                length=len(formatted_text),
                cost=f"${cost:.6f}"
            )

            return formatted_text, cost

        except Exception as e:
            logger.error(
                "formatting_failed",
                error=str(e),
                category=category
            )
            raise

    def format_category_simple(
        self,
        category: str,
        title: str,
        items: List[EnhancedNewsletterItem]
    ) -> str:
        """
        Format category message without AI (fallback).

        Args:
            category: Category name
            title: Category title
            items: List of enhanced items

        Returns:
            Formatted text string
        """
        lines = [
            f"**{title}**",
            "",
        ]

        # Add items
        for idx, item in enumerate(items, 1):
            lines.append(f"{idx}. **{item.viral_headline}**")
            lines.append(f"   {item.takeaway}")

            # Add engagement metrics if available
            if item.engagement_metrics:
                metrics_parts = []
                if "read_time" in item.engagement_metrics:
                    metrics_parts.append(item.engagement_metrics["read_time"])
                if "engagement" in item.engagement_metrics:
                    metrics_parts.append(item.engagement_metrics["engagement"])

                if metrics_parts:
                    lines.append(f"   {' · '.join(metrics_parts)}")

            lines.append(f"   🔗 [Read more]({item.url})")
            lines.append("")

        # Add separator
        lines.append("━━━━━━━━━━━━━━━━")

        return "\n".join(lines)
