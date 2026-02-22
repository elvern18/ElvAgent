"""
AI-powered takeaway generation.
Creates concise, think-out-loud reactions for each news item.
"""

from anthropic import AsyncAnthropic

from src.config.settings import settings
from src.models.newsletter import NewsletterItem
from src.publishing.enhancers.voice import VOICE_ANTI_PATTERNS, VOICE_SYSTEM_PROMPT
from src.utils.logger import get_logger

logger = get_logger("enhancer.takeaway")


class TakeawayGenerator:
    """
    Generate one-sentence takeaways using Claude Haiku.

    Creates brief, natural reactions using the shared voice.
    """

    SYSTEM_PROMPT = f"""{VOICE_SYSTEM_PROMPT}

your job is reacting to AI news in one sentence.
think out loud. no formulaic openers. just say what you actually think."""

    USER_PROMPT_TEMPLATE = f"""React to this AI news in one sentence:

Headline: {{headline}}
Summary: {{summary}}
Category: {{category}}

Rules:
- one sentence, under 30 words
- react like you're thinking out loud
- no formulaic openers
- admit uncertainty if you're not sure ("not sure about this but", "probably")
- be specific, not generic

Examples:
- "could cut training costs for small teams. that's the actual unlock here."
- "not sure this generalizes but the approach is interesting."
- "basically means you can run this on a laptop now. probably."
- "more money into India. pattern is getting hard to ignore."
- "sounds good in theory. want to see real benchmarks."
- "niche but hospitals actually need this."
- "interesting for linguistics research. not sure who else cares."

{VOICE_ANTI_PATTERNS}

Return ONLY the reaction. No quotes, no explanation."""

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
                max_tokens=80,
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
