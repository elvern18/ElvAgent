"""
AI-powered viral headline generation.
Transforms technical titles into engaging, clickable headlines.
"""
from anthropic import AsyncAnthropic
from typing import Optional
from src.config.settings import settings
from src.models.newsletter import NewsletterItem
from src.utils.logger import get_logger

logger = get_logger("enhancer.headline")


class HeadlineWriter:
    """
    Generate viral headlines using Claude Sonnet.

    Uses creative AI to transform technical titles into engaging
    social media headlines while maintaining factual accuracy.
    """

    SYSTEM_PROMPT = """You are a viral content headline writer specializing in AI/tech news.
Your headlines drive engagement while staying 100% factually accurate.
You write punchy, scannable headlines optimized for social media."""

    USER_PROMPT_TEMPLATE = """Transform this into an engaging headline:

Original Title: {title}
Category: {category}
Summary: {summary}

Requirements:
- 8-12 words maximum
- Include specific numbers/metrics when available (e.g., "$45M", "10x faster", "50% more accurate")
- Use power words appropriately: Breakthrough, Revolutionary, First, Major, etc.
- Create curiosity or urgency without clickbait
- Stay 100% factually accurate to the original content
- Start with appropriate category emoji

Category-Specific Guidelines:

[research] Focus on: Impact, methodology, performance gains
Examples:
- "New Vision Model Achieves SOTA" → "🔬 AI Achieves 10x Better Image Understanding Than GPT-4"
- "Study on Training Methods" → "🔬 Breakthrough: New Training Method Cuts Costs by 90%"

[funding] Focus on: Amount, company mission, market impact
Examples:
- "Startup Raises Series B" → "💰 AI Startup Raises $45M to Challenge OpenAI Dominance"
- "Investment Round" → "💰 $120M Bet on AI That Runs on Your Laptop"

[news] Focus on: What happened, immediate impact, key players
Examples:
- "Company Launches Product" → "🚨 Google Launches AI Tool That Actually Works Offline"
- "Executive Move" → "🚨 OpenAI Acquires Creator of Viral AI Tool"

[product] Focus on: What it does (not what it is), who benefits
Examples:
- "New ML Library Released" → "🚀 Library Cuts ML Model Size by 80% with Zero Accuracy Loss"
- "Tool Launch" → "🚀 First AI Tool That Runs on a $300 Laptop"

[regulation] Focus on: Impact on industry/users, timeline
Examples:
- "New Policy Announced" → "📜 New EU Rules Could Reshape How AI Companies Operate"
- "Legal Update" → "📜 Landmark Case Sets Precedent for AI Voice Rights"

Return ONLY the headline with emoji prefix. No quotes, no explanation, no additional text."""

    def __init__(self):
        """Initialize headline writer with Anthropic client."""
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"

    async def generate_headline(
        self,
        item: NewsletterItem,
        timeout: int = 30
    ) -> tuple[str, float]:
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
            summary=item.summary[:300]  # Truncate long summaries
        )

        logger.debug(
            "generating_headline",
            title=item.title[:50],
            category=item.category
        )

        try:
            # Call Claude API
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=100,
                system=self.SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                timeout=timeout
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
                cost=f"${cost:.4f}"
            )

            return headline, cost

        except Exception as e:
            logger.error(
                "headline_generation_failed",
                error=str(e),
                title=item.title[:50]
            )
            raise
