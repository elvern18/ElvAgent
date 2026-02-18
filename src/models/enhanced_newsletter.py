"""
Enhanced newsletter models for social media optimization.
Extends base newsletter with AI-generated engagement elements.
"""

from dataclasses import dataclass, field
from typing import Any

from src.models.newsletter import NewsletterItem


@dataclass
class EnhancedNewsletterItem:
    """
    Newsletter item enhanced with social media optimization.

    Includes AI-generated headlines, takeaways, and engagement metrics
    for maximum social media impact.
    """

    # Original data
    original_item: NewsletterItem

    # AI-enhanced fields
    viral_headline: str
    takeaway: str
    engagement_metrics: dict[str, Any] = field(default_factory=dict)

    # Metadata
    enhancement_method: str = "ai"  # "ai" or "template"
    enhancement_cost: float = 0.0

    @property
    def title(self) -> str:
        """Use viral headline as title."""
        return self.viral_headline

    @property
    def url(self) -> str:
        """Proxy to original URL."""
        return self.original_item.url

    @property
    def category(self) -> str:
        """Proxy to original category."""
        return self.original_item.category

    @property
    def relevance_score(self) -> int:
        """Proxy to original relevance score."""
        return self.original_item.relevance_score

    @property
    def source(self) -> str:
        """Proxy to original source."""
        return self.original_item.source

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "original_item": self.original_item.to_dict(),
            "viral_headline": self.viral_headline,
            "takeaway": self.takeaway,
            "engagement_metrics": self.engagement_metrics,
            "enhancement_method": self.enhancement_method,
            "enhancement_cost": self.enhancement_cost,
        }


@dataclass
class CategoryMessage:
    """Formatted message for a single category."""

    category: str
    emoji: str
    title: str
    items: list[EnhancedNewsletterItem]
    formatted_text: str
    item_count: int = 0

    def __post_init__(self):
        """Calculate item count."""
        self.item_count = len(self.items)


@dataclass
class EnhancementMetrics:
    """Metrics for tracking enhancement performance."""

    total_items: int = 0
    ai_enhanced: int = 0
    template_fallback: int = 0
    total_cost: float = 0.0
    total_time_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate AI enhancement success rate."""
        if self.total_items == 0:
            return 0.0
        return (self.ai_enhanced / self.total_items) * 100

    @property
    def avg_time_per_item(self) -> float:
        """Calculate average time per item."""
        if self.total_items == 0:
            return 0.0
        return self.total_time_seconds / self.total_items

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_items": self.total_items,
            "ai_enhanced": self.ai_enhanced,
            "template_fallback": self.template_fallback,
            "total_cost": self.total_cost,
            "total_time_seconds": self.total_time_seconds,
            "success_rate": self.success_rate,
            "avg_time_per_item": self.avg_time_per_item,
        }
