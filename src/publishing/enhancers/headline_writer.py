"""
AI-powered headline generation.
Transforms technical titles into concise, natural-sounding headlines.
"""

from anthropic import AsyncAnthropic

from src.config.settings import settings
from src.models.newsletter import NewsletterItem
from src.publishing.enhancers.voice import VOICE_ANTI_PATTERNS, VOICE_EXAMPLES, VOICE_SYSTEM_PROMPT
from src.utils.logger import get_logger

logger = get_logger("enhancer.headline")


class HeadlineWriter:
    """
    Generate headlines using Claude Sonnet.

    Uses the shared voice to create natural-sounding headlines
    while maintaining factual accuracy.
    """

    SYSTEM_PROMPT = f"""{VOICE_SYSTEM_PROMPT}

your job is writing one-line headlines for AI news items.
state what happened. be specific. use actual numbers and names.
8-15 words max. start with the category emoji."""

    USER_PROMPT_TEMPLATE = """Write a headline for this AI news item:

Original Title: {{title}}
Category: {{category}}
Summary: {{summary}}

Category emoji:
- research = 🔬
- funding = 💰
- news = 🔥
- product = 🚀
- regulation = 📜

Examples of the voice:
{examples}

{anti_patterns}

Return ONLY the headline with emoji prefix. No quotes, no explanation.""".format(
        examples="\n".join(f'- "{ex}"' for ex in VOICE_EXAMPLES[:6]),
        anti_patterns=VOICE_ANTI_PATTERNS,
    )

    def __init__(self):
        """Initialize headline writer with Anthropic client."""
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"

    async def generate_headline(self, item: NewsletterItem, timeout: int = 30) -> tuple[str, float]:
        """
        Generate viral headline for item.

        Args:
            item: Newsletter item to enhance
            timeout: API timeout in seconds

        Returns:
            Tuple of (headline, cost_in_dollars)

        Raises:
            Exception: If API call fails
        """
        # Format prompt
        prompt = self.USER_PROMPT_TEMPLATE.format(
            title=item.title,
            category=item.category,
            summary=item.summary[:300],  # Truncate long summaries
        )

        logger.debug("generating_headline", title=item.title[:50], category=item.category)

        try:
            # Call Claude API
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=100,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            )

            # Extract headline
            headline = response.content[0].text.strip()

            # Calculate cost
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = (input_tokens * 0.003 / 1000) + (output_tokens * 0.015 / 1000)

            logger.debug(
                "headline_generated",
                original=item.title[:50],
                headline=headline[:50],
                cost=f"${cost:.4f}",
            )

            return headline, cost

        except Exception as e:
            logger.error("headline_generation_failed", error=str(e), title=item.title[:50])
            raise
