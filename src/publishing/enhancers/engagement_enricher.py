"""
Engagement metrics extraction and enrichment.
Extracts social proof indicators from item metadata (no AI calls).
"""

from typing import Any

from src.models.newsletter import NewsletterItem
from src.utils.logger import get_logger

logger = get_logger("enhancer.engagement")


class EngagementEnricher:
    """
    Extract and format engagement metrics from item metadata.

    Processes metadata to create social proof indicators like
    upvotes, comments, read time, trending status, etc.
    """

    def enrich_metrics(self, item: NewsletterItem) -> dict[str, Any]:
        """
        Extract engagement metrics from item metadata.

        Args:
            item: Newsletter item with metadata

        Returns:
            Dictionary with formatted engagement metrics
        """
        metrics = {}
        metadata = item.metadata or {}

        # Reddit metrics
        if item.source == "reddit":
            metrics = self._extract_reddit_metrics(metadata)

        # HuggingFace metrics
        elif item.source == "huggingface":
            metrics = self._extract_huggingface_metrics(metadata)

        # TechCrunch metrics
        elif item.source == "techcrunch":
            metrics = self._extract_techcrunch_metrics(metadata)

        # ArXiv metrics
        elif item.source == "arxiv":
            metrics = self._extract_arxiv_metrics(metadata)

        # Read time removed — it's always "1 min" based on summary length, adds no value

        logger.debug("metrics_enriched", source=item.source, metrics=metrics)

        return metrics

    def _extract_reddit_metrics(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Extract Reddit-specific metrics."""
        metrics = {}

        # Flair indicates post type
        flair = metadata.get("flair", "")
        if flair:
            metrics["flair"] = flair

        # Author for attribution
        author = metadata.get("author", "")
        if author:
            metrics["author"] = f"u/{author}"

        return metrics

    def _extract_huggingface_metrics(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Extract HuggingFace-specific metrics."""
        metrics = {}

        # Comment count indicates engagement
        num_comments = metadata.get("num_comments", 0)
        if num_comments > 0:
            if num_comments >= 1000:
                metrics["engagement"] = f"💬 {num_comments / 1000:.1f}K comments"
            else:
                metrics["engagement"] = f"💬 {num_comments} comments"

        # ArXiv ID for paper reference (clean ID for inline use)
        arxiv_id = metadata.get("arxiv_id", "")
        if arxiv_id:
            clean_id = arxiv_id.replace("https://arxiv.org/abs/", "").replace("arxiv:", "")
            metrics["arxiv"] = clean_id

        return metrics

    def _extract_techcrunch_metrics(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Extract TechCrunch-specific metrics."""
        metrics = {}

        # Author for credibility
        author = metadata.get("author", "")
        if author:
            metrics["author"] = author

        # Tags for context
        tags = metadata.get("tags", [])
        if tags and len(tags) > 0:
            # Take first 3 tags
            metrics["tags"] = ", ".join(tags[:3])

        return metrics

    def _extract_arxiv_metrics(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Extract ArXiv-specific metrics."""
        metrics = {}

        # ArXiv ID (formatted as just the ID for inline use)
        arxiv_id = metadata.get("arxiv_id", "")
        if arxiv_id:
            # Strip any prefix, keep just the ID
            clean_id = arxiv_id.replace("https://arxiv.org/abs/", "").replace("arxiv:", "")
            metrics["arxiv"] = clean_id

        # Authors
        authors = metadata.get("authors", [])
        if authors and len(authors) > 0:
            # Show first author + et al if more
            if len(authors) == 1:
                metrics["authors"] = authors[0]
            else:
                metrics["authors"] = f"{authors[0]} et al."

        # PDF link
        pdf_url = metadata.get("pdf_url", "")
        if pdf_url:
            metrics["pdf"] = pdf_url

        return metrics

    def _estimate_read_time(self, text: str) -> str:
        """
        Estimate read time based on text length.

        Args:
            text: Text to estimate read time for

        Returns:
            Formatted read time string (e.g., "☕ 3-min read")
        """
        # Average reading speed: 200 words per minute
        word_count = len(text.split())
        minutes = max(1, round(word_count / 200))

        if minutes == 1:
            return "☕ 1-min read"
        else:
            return f"☕ {minutes}-min read"

    def format_engagement_line(self, metrics: dict[str, Any]) -> str:
        """
        Format metrics into a single engagement line for Telegram.

        Args:
            metrics: Dictionary of engagement metrics

        Returns:
            Formatted string like "💬 1.2K comments · ☕ 3-min read"
        """
        parts = []

        # Add engagement indicators
        if "engagement" in metrics:
            parts.append(metrics["engagement"])

        if "flair" in metrics:
            parts.append(f"[{metrics['flair']}]")

        # Add author if notable
        if "author" in metrics:
            parts.append(f"by {metrics['author']}")

        # Join with separator
        if len(parts) > 0:
            return " · ".join(parts)
        else:
            return ""
