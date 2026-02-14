"""
Base researcher class that all content researchers inherit from.
Defines the interface for content research operations.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from src.config.constants import MAX_ITEMS_PER_SOURCE, RESEARCH_TIME_WINDOW_HOURS
from src.utils.logger import get_logger

logger = get_logger("researcher")


class ContentItem:
    """Represents a single content item from research."""

    def __init__(
        self,
        title: str,
        url: str,
        source: str,
        category: str,
        relevance_score: int,
        summary: str,
        metadata: Optional[Dict[str, Any]] = None,
        published_date: Optional[datetime] = None
    ):
        """
        Initialize content item.

        Args:
            title: Item title
            url: Item URL
            source: Source name (e.g., 'arxiv', 'huggingface')
            category: Content category (e.g., 'research', 'product', 'funding')
            relevance_score: Relevance score from 1-10
            summary: Brief summary of the content
            metadata: Additional metadata (authors, tags, etc.)
            published_date: When the content was published
        """
        self.title = title
        self.url = url
        self.source = source
        self.category = category
        self.relevance_score = relevance_score
        self.summary = summary
        self.metadata = metadata or {}
        self.published_date = published_date or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "category": self.category,
            "relevance_score": self.relevance_score,
            "summary": self.summary,
            "metadata": self.metadata,
            "published_date": self.published_date.isoformat() if self.published_date else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContentItem":
        """Create from dictionary representation."""
        published_date = None
        if data.get("published_date"):
            published_date = datetime.fromisoformat(data["published_date"])

        return cls(
            title=data["title"],
            url=data["url"],
            source=data["source"],
            category=data["category"],
            relevance_score=data["relevance_score"],
            summary=data["summary"],
            metadata=data.get("metadata", {}),
            published_date=published_date
        )


class BaseResearcher(ABC):
    """
    Abstract base class for all content researchers.

    Each researcher implementation must:
    1. Fetch content from a specific source
    2. Parse and structure the content
    3. Score content relevance (1-10)
    4. Return top N items
    """

    def __init__(self, source_name: str, max_items: int = MAX_ITEMS_PER_SOURCE):
        """
        Initialize base researcher.

        Args:
            source_name: Name of the content source
            max_items: Maximum items to return
        """
        self.source_name = source_name
        self.max_items = max_items
        self.logger = get_logger(f"researcher.{source_name}")

    @abstractmethod
    async def fetch_content(self) -> List[ContentItem]:
        """
        Fetch and parse content from source.

        Returns:
            List of ContentItem objects

        Raises:
            Exception: If fetching or parsing fails
        """
        pass

    @abstractmethod
    def score_relevance(self, item: Dict[str, Any]) -> int:
        """
        Score content relevance from 1-10.

        Args:
            item: Raw content item dictionary

        Returns:
            Relevance score (1-10)
        """
        pass

    async def research(self) -> List[ContentItem]:
        """
        Main research method.
        Fetches content, scores relevance, and returns top items.

        Returns:
            List of top ContentItem objects sorted by relevance
        """
        self.logger.info("starting_research", source=self.source_name)

        try:
            # Fetch all content
            items = await self.fetch_content()

            self.logger.info(
                "content_fetched",
                source=self.source_name,
                item_count=len(items)
            )

            # Sort by relevance score (descending)
            items.sort(key=lambda x: x.relevance_score, reverse=True)

            # Return top N items
            top_items = items[:self.max_items]

            self.logger.info(
                "research_complete",
                source=self.source_name,
                returned_count=len(top_items)
            )

            return top_items

        except Exception as e:
            self.logger.error(
                "research_failed",
                source=self.source_name,
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    def is_within_time_window(
        self,
        published_date: datetime,
        hours: int = RESEARCH_TIME_WINDOW_HOURS
    ) -> bool:
        """
        Check if content is within the research time window.

        Args:
            published_date: When content was published
            hours: Time window in hours

        Returns:
            True if within window, False otherwise
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        return published_date >= cutoff

    def normalize_url(self, url: str) -> str:
        """
        Normalize URL by removing tracking parameters.

        Args:
            url: Raw URL

        Returns:
            Normalized URL
        """
        # Remove common tracking parameters
        tracking_params = ['utm_source', 'utm_medium', 'utm_campaign', 'ref', 'source']

        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        # Filter out tracking parameters
        filtered_params = {
            k: v for k, v in query_params.items()
            if k not in tracking_params
        }

        # Reconstruct URL
        new_query = urlencode(filtered_params, doseq=True)
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            ''  # Remove fragment
        ))

        return normalized
