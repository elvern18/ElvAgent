"""
AI-powered social media message formatting.
Creates clean, scannable Telegram messages with proper hierarchy.
"""

import json

from anthropic import AsyncAnthropic

from src.config.settings import settings
from src.models.enhanced_newsletter import EnhancedNewsletterItem
from src.publishing.enhancers.voice import VOICE_ANTI_PATTERNS, VOICE_SYSTEM_PROMPT
from src.utils.logger import get_logger

logger = get_logger("enhancer.formatter")


class SocialFormatter:
    """
    Format category messages using Claude Haiku.

    Creates clean Telegram messages using the shared voice,
    optimized for mobile reading.
    """

    SYSTEM_PROMPT = f"""{VOICE_SYSTEM_PROMPT}

your job is formatting AI news categories for Telegram.
write like you're texting someone. 2-3 short sentences for the lead story.
supporting stories get one line each. keep it casual, not pitch-y."""

    USER_PROMPT_TEMPLATE = f"""Format this category for Telegram:

Category: {{category}}
Title: {{title}}
Date: {{date}}
Items: {{items_json}}

Format:
1. Start with category title (e.g., "🔬 from the labs"). not bold, just emoji + lowercase.
2. LEAD STORY (item #1): 2-3 short sentences like you're texting someone. use the headline + takeaway as inspiration but rephrase naturally. link on its own line with "→" prefix.
3. SUPPORTING STORIES (items #2+): one line each, "→" prefix, casual description + (link). no label before them, just list them.
4. End with: ━━━━━━━━━━━━━━━━
5. Use Markdown links: [text](url)
6. NO bold text, NO numbered lists

{VOICE_ANTI_PATTERNS}

Example:

🔬 from the labs

GUI agent that scales from 2B to 235B params. works across mobile, desktop, web. curious how well it actually generalizes.
→ [link](url)

→ new jailbreak benchmark for South Asian languages. most safety tests ignore these. ([link](url))
→ fine-tuning vs prompting for text classification. prompting catching up faster than expected. ([link](url))

━━━━━━━━━━━━━━━━

Return ONLY the formatted message."""

    def __init__(self):
        """Initialize formatter with Anthropic client."""
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-haiku-4-5-20251001"

    async def format_category(
        self,
        category: str,
        title: str,
        items: list[EnhancedNewsletterItem],
        date: str,
        timeout: int = 30,
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
                "metrics": item.engagement_metrics,
            }
            items_data.append(item_dict)

        # Format prompt
        prompt = self.USER_PROMPT_TEMPLATE.format(
            category=category, title=title, date=date, items_json=json.dumps(items_data, indent=2)
        )

        logger.debug("formatting_category", category=category, item_count=len(items))

        try:
            # Call Claude API
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
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
                cost=f"${cost:.6f}",
            )

            return formatted_text, cost

        except Exception as e:
            logger.error("formatting_failed", error=str(e), category=category)
            raise

    def format_category_simple(
        self, category: str, title: str, items: list[EnhancedNewsletterItem]
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
            title,
            "",
        ]

        # Lead story (first item gets special treatment)
        if items:
            lead = items[0]
            lines.append(f"{lead.viral_headline}. {lead.takeaway}")
            lines.append(f"→ [link]({lead.url})")
            lines.append("")

        # Supporting stories
        if len(items) > 1:
            for item in items[1:]:
                lines.append(f"→ {item.viral_headline} ([link]({item.url}))")
            lines.append("")

        # Add separator
        lines.append("━━━━━━━━━━━━━━━━")

        return "\n".join(lines)
