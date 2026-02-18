"""
AI-powered "Why it matters" insight generation.
Creates concise, relatable takeaways for each news item.
"""

from anthropic import AsyncAnthropic

from src.config.settings import settings
from src.models.newsletter import NewsletterItem
from src.utils.logger import get_logger

logger = get_logger("enhancer.takeaway")


class TakeawayGenerator:
    """
    Generate "why it matters" insights using Claude Haiku.

    Creates brief, impactful explanations of real-world significance
    for technical content.
    """

    SYSTEM_PROMPT = """You generate concise "why it matters" insights for AI/tech news.
Your insights explain real-world impact in plain language."""

    USER_PROMPT_TEMPLATE = """Generate a one-sentence takeaway explaining why this matters:

Headline: {headline}
Summary: {summary}
Category: {category}

Format: "💡 Why it matters: [insight]"

Requirements:
- One sentence only
- Under 25 words
- Focus on real-world impact, not technical details
- Make it relatable to practitioners/businesses
- Avoid jargon and acronyms
- Be specific, not generic

Examples by category:

[research]
"💡 Why it matters: Could cut medical AI training time from months to weeks"
"💡 Why it matters: Makes state-of-the-art models accessible to small teams"

[funding]
"💡 Why it matters: Validates market demand for AI infrastructure solutions"
"💡 Why it matters: Could accelerate competition with established AI giants"

[news]
"💡 Why it matters: Sets legal precedent for AI-generated content rights"
"💡 Why it matters: Signals major shift in how tech giants approach AI"

[product]
"💡 Why it matters: Democratizes tools previously available only to big tech"
"💡 Why it matters: Solves the biggest pain point in ML deployment"

[regulation]
"💡 Why it matters: Will reshape how AI companies operate in Europe"
"💡 Why it matters: First major regulation addressing AI transparency"

Return ONLY the formatted takeaway starting with "💡 Why it matters:". No quotes, no explanation."""

    def __init__(self):
        """Initialize takeaway generator with Anthropic client."""
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-haiku-4-5-20251001"

    async def generate_takeaway(
        self, item: NewsletterItem, headline: str, timeout: int = 30
    ) -> tuple[str, float]:
        """
        Generate "why it matters" takeaway.

        Args:
            item: Newsletter item
            headline: Enhanced headline (for context)
            timeout: API timeout in seconds

        Returns:
            Tuple of (takeaway, cost_in_dollars)

        Raises:
            Exception: If API call fails
        """
        # Format prompt
        prompt = self.USER_PROMPT_TEMPLATE.format(
            headline=headline,
            summary=item.summary[:200],  # Truncate long summaries
            category=item.category,
        )

        logger.debug("generating_takeaway", headline=headline[:50], category=item.category)

        try:
            # Call Claude API
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=60,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            )

            # Extract takeaway
            takeaway = response.content[0].text.strip()

            # Calculate cost (Haiku is cheaper)
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = (input_tokens * 0.00025 / 1000) + (output_tokens * 0.00125 / 1000)

            logger.debug("takeaway_generated", takeaway=takeaway[:50], cost=f"${cost:.6f}")

            return takeaway, cost

        except Exception as e:
            logger.error("takeaway_generation_failed", error=str(e), headline=headline[:50])
            raise
