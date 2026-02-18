"""
Orchestrator for coordinating the full newsletter cycle.
Manages research → filter → enhance → publish → record phases.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Union, Tuple

from src.research.base import BaseResearcher, ContentItem
from src.publishing.base import BasePublisher, PublishResult
from src.core.content_pipeline import ContentPipeline
from src.core.state_manager import StateManager
from src.models.newsletter import Newsletter
from src.models.enhanced_newsletter import CategoryMessage, EnhancementMetrics
from src.publishing.content_enhancer import ContentEnhancer
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("orchestrator")


@dataclass
class CycleResult:
    """Result of a complete newsletter cycle."""

    success: bool
    newsletter: Optional[Newsletter]
    item_count: int
    filtered_count: int
    publish_results: List[PublishResult]
    total_cost: float
    error: Optional[str] = None
    enhancement_enabled: bool = False
    enhancement_metrics: Optional[EnhancementMetrics] = None

    @property
    def platforms_published(self) -> List[str]:
        """Get list of successfully published platforms."""
        return [
            result.platform
            for result in self.publish_results
            if result.success
        ]


class Orchestrator:
    """
    Orchestrate full newsletter cycle.

    Coordinates:
    1. Research phase - Fetch content from all sources (parallel)
    2. Filter phase - Process items through ContentPipeline
    3. Enhance phase - AI enhancement with ContentEnhancer (optional)
    4. Publish phase - Publish to all platforms (parallel, partial failure OK)
    5. Record phase - Store results in database
    """

    def __init__(
        self,
        state_manager: StateManager,
        researchers: List[BaseResearcher],
        publishers: List[BasePublisher],
        pipeline: ContentPipeline
    ):
        """
        Initialize orchestrator with dependencies.

        Args:
            state_manager: Database state manager
            researchers: List of content researchers
            publishers: List of platform publishers
            pipeline: Content pipeline for filtering/assembly
        """
        self.state_manager = state_manager
        self.researchers = researchers
        self.publishers = publishers
        self.pipeline = pipeline
        self.enhancer = ContentEnhancer() if settings.enable_content_enhancement else None

    async def run_cycle(self, mode: str = "test") -> CycleResult:
        """
        Execute full newsletter cycle.

        Args:
            mode: 'test' (no publishing) or 'production' (full cycle)

        Returns:
            CycleResult with success status and details
        """
        logger.info("cycle_start", mode=mode, researchers=len(self.researchers))

        try:
            # Phase 1: Research
            items = await self.research_phase()

            if len(items) == 0:
                logger.warning("no_items_found", skipping_cycle=True)
                return CycleResult(
                    success=True,
                    newsletter=None,
                    item_count=0,
                    filtered_count=0,
                    publish_results=[],
                    total_cost=0.0,
                    error="No items found"
                )

            # Phase 2: Filter and assemble
            newsletter = await self.filter_phase(items)

            # Phase 3: Enhancement (optional)
            enhancement_metrics = None
            content_to_publish = newsletter

            if settings.enable_content_enhancement and self.enhancer:
                category_messages, enhancement_metrics = await self.enhance_phase(newsletter)
                content_to_publish = category_messages

            # Phase 4: Publish (skip in test mode)
            publish_results = []
            if mode == "production":
                publish_results = await self.publish_phase(content_to_publish)

                # Phase 5: Record (only if at least one platform succeeded)
                if any(result.success for result in publish_results):
                    await self.record_phase(newsletter, publish_results, enhancement_metrics)
                else:
                    logger.error("all_platforms_failed", skipping_record=True)

            # Calculate total cost
            metrics = await self.state_manager.get_metrics()
            total_cost = metrics.get("total_cost", 0.0)

            logger.info(
                "cycle_complete",
                mode=mode,
                items=len(items),
                filtered=newsletter.item_count,
                published_platforms=len([r for r in publish_results if r.success]),
                cost=f"${total_cost:.4f}"
            )

            return CycleResult(
                success=True,
                newsletter=newsletter,
                item_count=len(items),
                filtered_count=newsletter.item_count,
                publish_results=publish_results,
                total_cost=total_cost,
                enhancement_enabled=bool(enhancement_metrics),
                enhancement_metrics=enhancement_metrics
            )

        except Exception as e:
            logger.error(
                "cycle_failed",
                error=str(e),
                error_type=type(e).__name__
            )

            return CycleResult(
                success=False,
                newsletter=None,
                item_count=0,
                filtered_count=0,
                publish_results=[],
                total_cost=0.0,
                error=str(e)
            )

    async def research_phase(self) -> List[ContentItem]:
        """
        Execute research phase with all researchers in parallel.

        Returns:
            Combined list of ContentItem objects from all sources

        Note:
            Continues even if some researchers fail (logs errors).
        """
        logger.info("research_phase_start", researcher_count=len(self.researchers))

        # Run all researchers in parallel with asyncio.gather
        tasks = [researcher.research() for researcher in self.researchers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect successful results
        all_items = []
        failed_count = 0

        for i, result in enumerate(results):
            researcher = self.researchers[i]

            if isinstance(result, Exception):
                # Research failed, log and continue
                logger.error(
                    "researcher_failed",
                    source=researcher.source_name,
                    error=str(result),
                    error_type=type(result).__name__
                )
                failed_count += 1
            else:
                # Research succeeded
                all_items.extend(result)
                logger.info(
                    "researcher_success",
                    source=researcher.source_name,
                    items=len(result)
                )

        logger.info(
            "research_phase_complete",
            total_items=len(all_items),
            successful_sources=len(self.researchers) - failed_count,
            failed_sources=failed_count
        )

        return all_items

    async def filter_phase(self, items: List[ContentItem]) -> Newsletter:
        """
        Execute filter phase through ContentPipeline.

        Args:
            items: Raw content items from research

        Returns:
            Assembled Newsletter object
        """
        logger.info("filter_phase_start", input_count=len(items))

        # Generate newsletter date (YYYY-MM-DD-HH)
        now = datetime.now()
        newsletter_date = now.strftime("%Y-%m-%d-%H")

        # Process through pipeline
        newsletter = await self.pipeline.process(items, newsletter_date)

        logger.info(
            "filter_phase_complete",
            output_count=newsletter.item_count,
            date=newsletter_date
        )

        return newsletter

    async def enhance_phase(
        self,
        newsletter: Newsletter
    ) -> Tuple[List[CategoryMessage], EnhancementMetrics]:
        """
        Execute enhancement phase with ContentEnhancer.

        Args:
            newsletter: Newsletter to enhance

        Returns:
            Tuple of (category_messages, enhancement_metrics)
        """
        logger.info("enhance_phase_start", item_count=newsletter.item_count)

        category_messages, metrics = await self.enhancer.enhance_newsletter(
            items=newsletter.items,
            date=newsletter.date,
            max_items_per_category=settings.max_items_per_category
        )

        logger.info(
            "enhance_phase_complete",
            categories=len(category_messages),
            ai_enhanced=metrics.ai_enhanced,
            cost=f"${metrics.total_cost:.4f}"
        )

        # Track cost in StateManager
        await self.state_manager.track_api_usage(
            api_name="content_enhancement",
            request_count=metrics.total_items,
            token_count=0,
            estimated_cost=metrics.total_cost
        )

        return category_messages, metrics

    async def publish_phase(
        self,
        content: Union[Newsletter, List[CategoryMessage]]
    ) -> List[PublishResult]:
        """
        Execute publish phase to all platforms in parallel.

        Args:
            content: Either Newsletter (standard) or List[CategoryMessage] (enhanced)

        Returns:
            List of PublishResult (partial failures OK)

        Note:
            Uses asyncio.gather with return_exceptions=True to allow partial success.
        """
        # Detect content type
        is_enhanced = isinstance(content, list) and len(content) > 0 and isinstance(content[0], CategoryMessage)

        logger.info(
            "publish_phase_start",
            publisher_count=len(self.publishers),
            enhanced=is_enhanced
        )

        if len(self.publishers) == 0:
            logger.warning("no_publishers_configured", skipping_publish=True)
            return []

        # Publish to all platforms in parallel
        tasks = []
        for publisher in self.publishers:
            if is_enhanced and hasattr(publisher, 'publish_enhanced'):
                # Use enhanced publishing if available
                tasks.append(publisher.publish_enhanced(content))
            else:
                # Fallback to standard publishing
                newsletter = content if isinstance(content, Newsletter) else self._category_to_newsletter(content)
                tasks.append(publisher.publish_newsletter(newsletter))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to PublishResult
        publish_results = []
        for i, result in enumerate(results):
            publisher = self.publishers[i]

            if isinstance(result, Exception):
                # Publishing crashed
                publish_results.append(
                    PublishResult(
                        platform=publisher.platform_name,
                        success=False,
                        error=str(result)
                    )
                )
                logger.error(
                    "publisher_crashed",
                    platform=publisher.platform_name,
                    error=str(result)
                )
            else:
                # Got PublishResult
                publish_results.append(result)

        # Log summary
        successful = sum(1 for r in publish_results if r.success)
        failed = len(publish_results) - successful

        logger.info(
            "publish_phase_complete",
            successful=successful,
            failed=failed,
            platforms=[r.platform for r in publish_results if r.success]
        )

        return publish_results

    def _category_to_newsletter(self, category_messages: List[CategoryMessage]) -> Newsletter:
        """
        Convert CategoryMessage back to Newsletter for publishers without enhance support.

        Args:
            category_messages: List of CategoryMessage objects

        Returns:
            Newsletter object
        """
        all_items = []
        for msg in category_messages:
            all_items.extend([item.original_item for item in msg.items])

        date = category_messages[0].items[0].original_item.published_date.strftime("%Y-%m-%d-%H") if category_messages and category_messages[0].items else datetime.now().strftime("%Y-%m-%d-%H")

        return Newsletter(
            date=date,
            items=all_items,
            summary=f"AI-enhanced newsletter with {len(all_items)} items",
            item_count=len(all_items)
        )

    async def record_phase(
        self,
        newsletter: Newsletter,
        publish_results: List[PublishResult],
        enhancement_metrics: Optional[EnhancementMetrics] = None
    ):
        """
        Record newsletter and items to database.

        Args:
            newsletter: Published newsletter
            publish_results: Publishing results from all platforms
            enhancement_metrics: Optional enhancement metrics

        Note:
            Logs errors but doesn't crash if database write fails.
        """
        logger.info("record_phase_start", items=newsletter.item_count)

        if enhancement_metrics:
            logger.info(
                "enhancement_metrics",
                ai_enhanced=enhancement_metrics.ai_enhanced,
                success_rate=f"{enhancement_metrics.success_rate:.1f}%",
                cost=f"${enhancement_metrics.total_cost:.4f}"
            )

        try:
            # Get successful platforms
            platforms_published = [
                result.platform
                for result in publish_results
                if result.success
            ]

            # Create newsletter record
            newsletter_id = await self.state_manager.create_newsletter_record(
                newsletter_date=newsletter.date,
                item_count=newsletter.item_count,
                platforms_published=platforms_published,
                skip_reason=None
            )

            # Store each item
            for item in newsletter.items:
                try:
                    await self.state_manager.store_content({
                        "url": item.url,
                        "title": item.title,
                        "source": item.source,
                        "category": item.category,
                        "newsletter_date": newsletter.date,
                        "metadata": item.metadata
                    })
                except Exception as e:
                    logger.warning(
                        "item_storage_failed",
                        title=item.title,
                        error=str(e)
                    )

            # Log publishing attempts
            for result in publish_results:
                await self.state_manager.log_publishing_attempt(
                    newsletter_id=newsletter_id,
                    platform=result.platform,
                    status="success" if result.success else "failed",
                    error_message=result.error,
                    attempt_count=1
                )

            logger.info(
                "record_phase_complete",
                newsletter_id=newsletter_id,
                items_stored=newsletter.item_count
            )

        except Exception as e:
            logger.error(
                "record_phase_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            # Don't re-raise - recording failure shouldn't crash the cycle
