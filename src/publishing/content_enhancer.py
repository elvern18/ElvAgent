"""
ContentEnhancer orchestrator for sequential newsletter enhancement.

Coordinates HeadlineWriter, TakeawayGenerator, EngagementEnricher, and SocialFormatter
to transform NewsletterItems into optimized social media content with retry logic
and template fallbacks.
"""

import time
from collections import defaultdict

from src.models.enhanced_newsletter import (
    CategoryMessage,
    EnhancedNewsletterItem,
    EnhancementMetrics,
)
from src.models.newsletter import NewsletterItem
from src.publishing.enhancers.engagement_enricher import EngagementEnricher
from src.publishing.enhancers.headline_writer import HeadlineWriter
from src.publishing.enhancers.social_formatter import SocialFormatter
from src.publishing.enhancers.takeaway_generator import TakeawayGenerator
from src.publishing.enhancers.templates import (
    get_category_emoji,
    get_category_title,
    get_template_headline,
    get_template_takeaway,
)
from src.utils.logger import get_logger
from src.utils.retry import retry_async

logger = get_logger("content_enhancer")


class ContentEnhancer:
    """
    Orchestrates sequential enhancement of newsletter items.

    Flow:
    1. Enhance items one-by-one (sequential, NOT parallel)
    2. For each item: headline → takeaway → metrics
    3. Retry 3x with exponential backoff (1s, 2s, 4s)
    4. Fallback to templates on failure
    5. Group by category (max 5 items per category)
    6. Format each category with AI
    7. Return (List[CategoryMessage], EnhancementMetrics)
    """

    def __init__(self):
        """Initialize enhancer with all sub-components."""
        self.headline_writer = HeadlineWriter()
        self.takeaway_generator = TakeawayGenerator()
        self.engagement_enricher = EngagementEnricher()
        self.social_formatter = SocialFormatter()

        logger.info("content_enhancer_initialized")

    async def enhance_newsletter(
        self, items: list[NewsletterItem], date: str, max_items_per_category: int = 5
    ) -> tuple[list[CategoryMessage], EnhancementMetrics]:
        """
        Enhance newsletter items and format category messages.

        Args:
            items: List of NewsletterItem objects to enhance
            date: Newsletter date (e.g., "2026-02-17")
            max_items_per_category: Maximum items per category (default: 5)

        Returns:
            Tuple of (list of CategoryMessage objects, EnhancementMetrics)
        """
        logger.info(
            "enhancement_started",
            total_items=len(items),
            date=date,
            max_per_category=max_items_per_category,
        )

        # Initialize metrics
        metrics = EnhancementMetrics(total_items=len(items))
        start_time = time.time()

        # Step 1: Enhance each item sequentially
        enhanced_items = []
        for idx, item in enumerate(items, 1):
            logger.debug("enhancing_item", item_num=idx, total=len(items), title=item.title[:50])

            enhanced_item = await self._enhance_single_item(item, metrics)
            enhanced_items.append(enhanced_item)

        # Step 2: Group by category and take top items
        grouped_items = self._group_by_category(enhanced_items, max_items_per_category)

        logger.info(
            "items_grouped",
            categories=list(grouped_items.keys()),
            total_after_grouping=sum(len(items) for items in grouped_items.values()),
        )

        # Step 3: Format each category
        category_messages = []
        for category, category_items in grouped_items.items():
            logger.debug("formatting_category", category=category, item_count=len(category_items))

            category_message = await self._format_category_message(
                category=category, items=category_items, date=date, metrics=metrics
            )
            category_messages.append(category_message)

        # Calculate final metrics
        metrics.total_time_seconds = time.time() - start_time

        logger.info(
            "enhancement_completed",
            total_items=metrics.total_items,
            ai_enhanced=metrics.ai_enhanced,
            template_fallback=metrics.template_fallback,
            success_rate=f"{metrics.success_rate:.1f}%",
            total_cost=f"${metrics.total_cost:.4f}",
            total_time=f"{metrics.total_time_seconds:.2f}s",
            categories=len(category_messages),
        )

        return category_messages, metrics

    async def _enhance_single_item(
        self, item: NewsletterItem, metrics: EnhancementMetrics
    ) -> EnhancedNewsletterItem:
        """
        Enhance a single item with retry logic and template fallback.

        Args:
            item: NewsletterItem to enhance
            metrics: EnhancementMetrics to update

        Returns:
            EnhancedNewsletterItem (either AI-enhanced or template-based)
        """
        try:
            # Try AI enhancement with retry (3 attempts, exponential backoff)
            enhanced_item = await retry_async(
                self._enhance_with_ai, item, max_attempts=3, min_wait=1.0, max_wait=4.0
            )

            # Success: increment AI counter and track cost
            metrics.ai_enhanced += 1
            metrics.total_cost += enhanced_item.enhancement_cost

            logger.debug(
                "item_enhanced_with_ai",
                title=item.title[:50],
                cost=f"${enhanced_item.enhancement_cost:.4f}",
            )

            return enhanced_item

        except Exception as e:
            # All retries failed: fallback to template
            logger.warning(
                "ai_enhancement_failed_using_template",
                title=item.title[:50],
                error=str(e),
                error_type=type(e).__name__,
            )

            enhanced_item = self._enhance_with_template(item)
            metrics.template_fallback += 1

            return enhanced_item

    async def _enhance_with_ai(self, item: NewsletterItem) -> EnhancedNewsletterItem:
        """
        Enhance item using AI agents (no internal retry).

        Args:
            item: NewsletterItem to enhance

        Returns:
            EnhancedNewsletterItem with AI-generated content

        Raises:
            Exception: If any AI call fails (handled by retry_async)
        """
        # Generate headline
        headline, cost1 = await self.headline_writer.generate_headline(item)

        # Generate takeaway (uses headline for context)
        takeaway, cost2 = await self.takeaway_generator.generate_takeaway(item, headline)

        # Extract engagement metrics (no API call)
        metrics = self.engagement_enricher.enrich_metrics(item)

        return EnhancedNewsletterItem(
            original_item=item,
            viral_headline=headline,
            takeaway=takeaway,
            engagement_metrics=metrics,
            enhancement_method="ai",
            enhancement_cost=cost1 + cost2,
        )

    def _enhance_with_template(self, item: NewsletterItem) -> EnhancedNewsletterItem:
        """
        Enhance item using templates (fallback, no AI calls).

        Args:
            item: NewsletterItem to enhance

        Returns:
            EnhancedNewsletterItem with template-generated content
        """
        headline = get_template_headline(item)
        takeaway = get_template_takeaway(item)
        metrics = self.engagement_enricher.enrich_metrics(item)

        return EnhancedNewsletterItem(
            original_item=item,
            viral_headline=headline,
            takeaway=takeaway,
            engagement_metrics=metrics,
            enhancement_method="template",
            enhancement_cost=0.0,
        )

    def _group_by_category(
        self, items: list[EnhancedNewsletterItem], max_per_category: int = 5
    ) -> dict[str, list[EnhancedNewsletterItem]]:
        """
        Group items by category and take top N per category.

        Args:
            items: List of enhanced items
            max_per_category: Maximum items to keep per category

        Returns:
            Dictionary mapping category to list of top items
        """
        # Group by category
        grouped = defaultdict(list)
        for item in items:
            grouped[item.category].append(item)

        # Sort each category by relevance_score (descending) and take top N
        result = {}
        for category, category_items in grouped.items():
            sorted_items = sorted(category_items, key=lambda x: x.relevance_score, reverse=True)
            result[category] = sorted_items[:max_per_category]

        logger.debug(
            "items_grouped_by_category",
            categories={cat: len(items) for cat, items in result.items()},
        )

        return result

    async def _format_category_message(
        self,
        category: str,
        items: list[EnhancedNewsletterItem],
        date: str,
        metrics: EnhancementMetrics,
    ) -> CategoryMessage:
        """
        Format category message using AI or fallback to simple formatting.

        Args:
            category: Category name
            items: List of enhanced items in this category
            date: Newsletter date
            metrics: EnhancementMetrics to update with formatting cost

        Returns:
            CategoryMessage with formatted text
        """
        # Get category metadata
        emoji = get_category_emoji(category)
        title = get_category_title(category, date)

        try:
            # Try AI formatting with retry (3 attempts)
            formatted_text, cost = await retry_async(
                self.social_formatter.format_category,
                category,
                title,
                items,
                date,
                max_attempts=3,
                min_wait=1.0,
                max_wait=4.0,
            )

            metrics.total_cost += cost

            logger.debug("category_formatted_with_ai", category=category, cost=f"${cost:.4f}")

        except Exception as e:
            # Fallback to simple formatting
            logger.warning(
                "ai_formatting_failed_using_simple",
                category=category,
                error=str(e),
                error_type=type(e).__name__,
            )

            formatted_text = self.social_formatter.format_category_simple(
                category=category, title=title, items=items
            )

        return CategoryMessage(
            category=category, emoji=emoji, title=title, items=items, formatted_text=formatted_text
        )
