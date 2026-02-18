"""
Content pipeline for processing research items into newsletters.
Handles filtering, deduplication, conversion, and newsletter assembly.
"""

from datetime import datetime, timedelta

from anthropic import AsyncAnthropic

from src.config.constants import (
    MIN_RELEVANCE_SCORE,
    MIN_SIGNIFICANT_ITEMS,
    MODEL_COSTS,
    RESEARCH_TIME_WINDOW_HOURS,
)
from src.config.settings import settings
from src.core.state_manager import StateManager
from src.models.newsletter import Newsletter, NewsletterItem
from src.research.base import ContentItem
from src.utils.logger import get_logger

logger = get_logger("content_pipeline")


class ContentPipeline:
    """
    Multi-stage content pipeline: filter → convert → summarize → assemble.

    Transforms ContentItem[] from research into Newsletter object ready for publishing.
    """

    def __init__(self, state_manager: StateManager):
        """
        Initialize content pipeline.

        Args:
            state_manager: StateManager instance for deduplication
        """
        self.state_manager = state_manager
        self.client = (
            AsyncAnthropic(api_key=settings.anthropic_api_key)
            if settings.anthropic_api_key
            else None
        )

    async def process(self, items: list[ContentItem], date: str) -> Newsletter:
        """
        Main pipeline: filter → convert → summarize → assemble.

        Args:
            items: Raw content items from research
            date: Newsletter date (YYYY-MM-DD-HH)

        Returns:
            Complete Newsletter object
        """
        logger.info("pipeline_start", input_count=len(items), date=date)

        # Stage 1: Deduplication
        unique_items = await self.deduplicate(items)
        logger.info("deduplication_complete", unique_count=len(unique_items))

        # Stage 2: Relevance filtering
        relevant_items = self.filter_by_relevance(unique_items)
        logger.info("relevance_filter_complete", relevant_count=len(relevant_items))

        # Stage 3: Time filtering
        recent_items = self.filter_by_time(relevant_items)
        logger.info("time_filter_complete", recent_count=len(recent_items))

        # Stage 4: Convert to NewsletterItem
        newsletter_items = self.convert_to_newsletter_items(recent_items)

        # Stage 5: Generate summary
        summary = await self.generate_summary(newsletter_items, date)

        # Stage 6: Assemble newsletter
        newsletter = self.assemble_newsletter(newsletter_items, summary, date)

        logger.info("pipeline_complete", final_count=newsletter.item_count, date=date)

        return newsletter

    async def deduplicate(self, items: list[ContentItem]) -> list[ContentItem]:
        """
        Remove duplicate items using StateManager.

        Args:
            items: Content items to deduplicate

        Returns:
            List of unique items
        """
        unique_items = []

        for item in items:
            try:
                is_duplicate = await self.state_manager.check_duplicate(
                    url=item.url, title=item.title
                )

                if not is_duplicate:
                    unique_items.append(item)
                else:
                    logger.debug("duplicate_filtered", title=item.title, source=item.source)

            except Exception as e:
                # Log error but continue (assume not duplicate to be safe)
                logger.warning("duplicate_check_failed", error=str(e), title=item.title)
                unique_items.append(item)

        return unique_items

    def filter_by_relevance(self, items: list[ContentItem]) -> list[ContentItem]:
        """
        Filter items by relevance score threshold.

        Args:
            items: Content items to filter

        Returns:
            Items with score >= MIN_RELEVANCE_SCORE
        """
        filtered = [item for item in items if item.relevance_score >= MIN_RELEVANCE_SCORE]

        # Log filtered items
        for item in items:
            if item.relevance_score < MIN_RELEVANCE_SCORE:
                logger.debug(
                    "low_relevance_filtered",
                    title=item.title,
                    score=item.relevance_score,
                    threshold=MIN_RELEVANCE_SCORE,
                )

        return filtered

    def filter_by_time(
        self, items: list[ContentItem], hours: int = RESEARCH_TIME_WINDOW_HOURS
    ) -> list[ContentItem]:
        """
        Filter items by publication time window.

        Args:
            items: Content items to filter
            hours: Time window in hours (default from constants)

        Returns:
            Items published within the time window
        """
        cutoff = datetime.now() - timedelta(hours=hours)

        filtered = [item for item in items if item.published_date and item.published_date >= cutoff]

        # Log filtered items
        for item in items:
            if not item.published_date or item.published_date < cutoff:
                logger.debug(
                    "old_content_filtered",
                    title=item.title,
                    published_date=item.published_date.isoformat()
                    if item.published_date
                    else "unknown",
                    cutoff=cutoff.isoformat(),
                )

        return filtered

    def convert_to_newsletter_items(self, items: list[ContentItem]) -> list[NewsletterItem]:
        """
        Convert ContentItem objects to NewsletterItem objects.

        Args:
            items: ContentItem list

        Returns:
            NewsletterItem list (1:1 field mapping)
        """
        newsletter_items = []

        for item in items:
            try:
                newsletter_item = NewsletterItem(
                    title=item.title,
                    url=item.url,
                    summary=item.summary,
                    category=item.category,
                    source=item.source,
                    relevance_score=item.relevance_score,
                    published_date=item.published_date,
                    metadata=item.metadata,
                )
                newsletter_items.append(newsletter_item)

            except Exception as e:
                logger.warning("item_conversion_failed", error=str(e), title=item.title)
                continue

        return newsletter_items

    async def generate_summary(self, items: list[NewsletterItem], date: str) -> str:
        """
        Generate newsletter summary using Claude API.

        Args:
            items: Newsletter items to summarize
            date: Newsletter date

        Returns:
            Summary text (with warning if <3 items)
        """
        # Add warning if below threshold
        warning = ""
        if len(items) < MIN_SIGNIFICANT_ITEMS:
            warning = f"⚠️ Note: Only {len(items)} item{'s' if len(items) != 1 else ''} found (recommended: {MIN_SIGNIFICANT_ITEMS}+)\n\n"

        # Handle empty items
        if len(items) == 0:
            return warning + "No significant AI developments found in this cycle."

        # Generate summary if Claude API is configured
        if not self.client or not settings.anthropic_api_key:
            logger.warning("claude_api_not_configured", using_fallback=True)
            return warning + self._generate_fallback_summary(items)

        try:
            summary = await self._call_claude_api(items, date)
            return warning + summary

        except Exception as e:
            logger.error("summary_generation_failed", error=str(e), using_fallback=True)
            return warning + self._generate_fallback_summary(items)

    async def _call_claude_api(self, items: list[NewsletterItem], date: str) -> str:
        """
        Call Claude API to generate summary.

        Args:
            items: Newsletter items
            date: Newsletter date

        Returns:
            Generated summary text
        """
        # Build items list for prompt
        items_text = []
        for i, item in enumerate(items, 1):
            items_text.append(
                f"{i}. **{item.title}** ({item.category})\n"
                f"   Source: {item.source}\n"
                f"   Summary: {item.summary}\n"
            )

        items_list = "\n".join(items_text)

        # Construct prompt
        prompt = f"""You are an AI news curator. Generate a brief, engaging summary for today's AI newsletter.

Newsletter Date: {date}
Item Count: {len(items)}

Items:
{items_list}

Generate 2-3 sentences highlighting the most significant developments. Be concise and focus on what matters to AI practitioners and researchers. Do not use emojis."""

        logger.info("calling_claude_api", model=settings.anthropic_model)

        # Call Claude API
        message = await self.client.messages.create(
            model=settings.anthropic_model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract summary
        summary = message.content[0].text.strip()

        # Track API usage
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens

        # Calculate cost
        model_name = settings.anthropic_model
        costs = MODEL_COSTS.get(model_name, {"input": 0, "output": 0})
        estimated_cost = (input_tokens / 1000) * costs["input"] + (output_tokens / 1000) * costs[
            "output"
        ]

        await self.state_manager.track_api_usage(
            api_name="anthropic",
            request_count=1,
            token_count=input_tokens + output_tokens,
            estimated_cost=estimated_cost,
        )

        logger.info(
            "summary_generated", tokens=input_tokens + output_tokens, cost=f"${estimated_cost:.4f}"
        )

        return summary

    def _generate_fallback_summary(self, items: list[NewsletterItem]) -> str:
        """
        Generate simple fallback summary without API.

        Args:
            items: Newsletter items

        Returns:
            Template-based summary
        """
        if len(items) == 1:
            return f"Today's highlight: {items[0].title} from {items[0].source}."

        categories = list({item.category for item in items})
        sources = list({item.source for item in items})

        return (
            f"Today's AI highlights include {len(items)} items "
            f"across {len(categories)} categories "
            f"({', '.join(categories)}) from {', '.join(sources)}."
        )

    def assemble_newsletter(
        self, items: list[NewsletterItem], summary: str, date: str
    ) -> Newsletter:
        """
        Assemble final Newsletter object.

        Args:
            items: Newsletter items
            summary: Newsletter summary
            date: Newsletter date (YYYY-MM-DD-HH)

        Returns:
            Complete Newsletter object
        """
        newsletter = Newsletter(date=date, items=items, summary=summary, item_count=len(items))

        logger.info("newsletter_assembled", date=date, item_count=len(items))

        return newsletter
