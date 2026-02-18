"""
ArXiv researcher for fetching latest AI/ML papers.
Fetches from ArXiv RSS feed and scores relevance.
"""

from datetime import datetime
from typing import Any

import feedparser
import httpx

from src.research.base import BaseResearcher, ContentItem


class ArXivResearcher(BaseResearcher):
    """Researcher for ArXiv AI/ML papers."""

    RSS_URL = "https://export.arxiv.org/rss/cs.AI"

    def __init__(self, max_items: int = 5):
        """Initialize ArXiv researcher."""
        super().__init__(source_name="arxiv", max_items=max_items)

    async def fetch_content(self) -> list[ContentItem]:
        """
        Fetch and parse ArXiv RSS feed.

        Returns:
            List of ContentItem objects
        """
        items = []

        try:
            # Fetch RSS feed
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.RSS_URL)
                response.raise_for_status()

            # Parse RSS
            feed = feedparser.parse(response.content)

            self.logger.info("feed_parsed", source=self.source_name, entry_count=len(feed.entries))

            for entry in feed.entries:
                try:
                    # Parse entry
                    item_data = self._parse_entry(entry)

                    # Skip if outside time window
                    if not self.is_within_time_window(item_data["published_date"]):
                        continue

                    # Score relevance
                    relevance_score = self.score_relevance(item_data)

                    # Skip low-relevance items
                    if relevance_score < 5:
                        continue

                    # Create ContentItem
                    content_item = ContentItem(
                        title=item_data["title"],
                        url=self.normalize_url(item_data["url"]),
                        source=self.source_name,
                        category="research",
                        relevance_score=relevance_score,
                        summary=item_data["summary"],
                        metadata={
                            "authors": item_data.get("authors", []),
                            "pdf_url": item_data.get("pdf_url"),
                            "arxiv_id": item_data.get("arxiv_id"),
                        },
                        published_date=item_data["published_date"],
                    )

                    items.append(content_item)

                except Exception as e:
                    self.logger.warning(
                        "entry_parse_failed",
                        error=str(e),
                        entry_title=entry.get("title", "unknown"),
                    )
                    continue

        except Exception as e:
            self.logger.error("feed_fetch_failed", source=self.source_name, error=str(e))
            raise

        return items

    def _parse_entry(self, entry: Any) -> dict[str, Any]:
        """
        Parse RSS entry into structured data.

        Args:
            entry: feedparser entry

        Returns:
            Dictionary with parsed data
        """
        # Extract title
        title = entry.get("title", "").strip()

        # Extract URL and PDF URL
        url = entry.get("link", "")
        arxiv_id = url.split("/")[-1] if url else ""
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else ""

        # Extract authors
        authors = []
        if "authors" in entry:
            authors = [author.get("name", "") for author in entry.authors]
        elif "author" in entry:
            authors = [entry.author]

        # Extract summary
        summary = entry.get("summary", "").strip()

        # Truncate summary if too long
        if len(summary) > 500:
            summary = summary[:497] + "..."

        # Parse published date
        published_date = datetime.now()
        if "published_parsed" in entry and entry.published_parsed:
            try:
                import time

                published_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
            except Exception:
                pass

        return {
            "title": title,
            "url": url,
            "pdf_url": pdf_url,
            "arxiv_id": arxiv_id,
            "authors": authors,
            "summary": summary,
            "published_date": published_date,
        }

    def score_relevance(self, item: dict[str, Any]) -> int:
        """
        Score relevance from 1-10.

        Prioritizes:
        - Novel architectures (transformers, diffusion, etc.)
        - Code releases
        - Practical applications
        - High-impact topics (LLMs, multimodal, agents)

        Args:
            item: Parsed item dictionary

        Returns:
            Relevance score (1-10)
        """
        score = 5  # Base score

        title = item["title"].lower()
        summary = item["summary"].lower()
        text = f"{title} {summary}"

        # High-impact keywords (+2)
        high_impact = [
            "llm",
            "large language model",
            "transformer",
            "diffusion",
            "multimodal",
            "agent",
            "reasoning",
            "gpt",
            "claude",
            "bert",
            "vision-language",
        ]
        if any(keyword in text for keyword in high_impact):
            score += 2

        # Code/practical keywords (+1)
        practical = ["code", "implementation", "open-source", "benchmark", "dataset", "application"]
        if any(keyword in text for keyword in practical):
            score += 1

        # Novel/breakthrough keywords (+1)
        novel = [
            "novel",
            "breakthrough",
            "state-of-the-art",
            "sota",
            "outperform",
            "surpass",
            "improve",
        ]
        if any(keyword in text for keyword in novel):
            score += 1

        # Technical depth keywords (+1)
        technical = [
            "architecture",
            "training",
            "optimization",
            "fine-tuning",
            "pre-training",
            "alignment",
        ]
        if any(keyword in text for keyword in technical):
            score += 1

        # Penalize purely theoretical (-1)
        if "theoretical" in text or "proof" in text:
            score -= 1

        # Ensure score is within 1-10
        score = max(1, min(10, score))

        return score
