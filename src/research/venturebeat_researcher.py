"""
VentureBeat researcher for fetching enterprise AI news.
Fetches from VentureBeat AI RSS feed and scores relevance.
"""

import re
from datetime import datetime
from typing import Any

import feedparser
import httpx

from src.research.base import BaseResearcher, ContentItem


class VentureBeatResearcher(BaseResearcher):
    """Researcher for VentureBeat AI news."""

    RSS_URL = "https://venturebeat.com/category/ai/feed/"

    def __init__(self, max_items: int = 5):
        """Initialize VentureBeat researcher."""
        super().__init__(source_name="venturebeat", max_items=max_items)

    async def fetch_content(self) -> list[ContentItem]:
        """
        Fetch and parse VentureBeat RSS feed.

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

                    # Skip if outside time window (use 24 hours for VentureBeat)
                    if not self.is_within_time_window(item_data["published_date"], hours=24):
                        continue

                    # Score relevance
                    relevance_score = self.score_relevance(item_data)

                    # Skip low-relevance items
                    if relevance_score < 5:
                        continue

                    # Detect category from content
                    category = self._detect_category(item_data)

                    # Create ContentItem
                    content_item = ContentItem(
                        title=item_data["title"],
                        url=self.normalize_url(item_data["url"]),
                        source=self.source_name,
                        category=category,
                        relevance_score=relevance_score,
                        summary=item_data["summary"],
                        metadata={
                            "author": item_data.get("author"),
                            "tags": item_data.get("tags", []),
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

        # Extract URL
        url = entry.get("link", "")

        # Extract author
        author = entry.get("author", "unknown")

        # Extract tags
        tags = []
        if "tags" in entry:
            tags = [tag.get("term", "") for tag in entry.tags]

        # Extract summary/content
        summary = entry.get("summary", "").strip()

        # Remove HTML tags from summary
        summary = re.sub(r"<[^>]+>", "", summary)

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
            "author": author,
            "tags": tags,
            "summary": summary,
            "published_date": published_date,
        }

    def _detect_category(self, item: dict[str, Any]) -> str:
        """
        Detect category from content.

        Categories:
        - funding: Fundraising, investments, acquisitions
        - product: Product launches, releases, announcements
        - regulation: Policy, law, regulation
        - news: General news (default)

        Args:
            item: Parsed item dictionary

        Returns:
            Category string
        """
        title = item["title"].lower()
        summary = item["summary"].lower()
        text = f"{title} {summary}"

        # Funding detection
        funding_keywords = [
            "raises",
            "raised",
            "funding",
            "investment",
            "series",
            "million",
            "billion",
            "venture",
            "acquires",
            "acquired",
            "acquisition",
            "buys",
            "merger",
            "valuation",
        ]
        if any(keyword in text for keyword in funding_keywords):
            return "funding"

        # Product detection
        product_keywords = [
            "launches",
            "launched",
            "release",
            "released",
            "announces",
            "announced",
            "unveils",
            "debuts",
            "introduces",
            "updates",
            "new feature",
            "new model",
            "new tool",
        ]
        if any(keyword in text for keyword in product_keywords):
            return "product"

        # Regulation detection
        regulation_keywords = [
            "regulation",
            "policy",
            "law",
            "lawsuit",
            "legal",
            "congress",
            "senate",
            "government",
            "ban",
            "restricts",
        ]
        if any(keyword in text for keyword in regulation_keywords):
            return "regulation"

        # Default to news
        return "news"

    def score_relevance(self, item: dict[str, Any]) -> int:
        """
        Score relevance from 1-10.

        Prioritizes:
        - Large funding rounds (>$50M)
        - Major product launches
        - Breakthrough technology
        - Major companies (OpenAI, Anthropic, Google, etc.)

        Args:
            item: Parsed item dictionary

        Returns:
            Relevance score (1-10)
        """
        score = 5  # Base score

        title = item["title"].lower()
        summary = item["summary"].lower()
        text = f"{title} {summary}"

        # Major companies (+2)
        major_companies = [
            "openai",
            "anthropic",
            "google",
            "deepmind",
            "meta",
            "microsoft",
            "apple",
            "amazon",
            "nvidia",
            "tesla",
        ]
        if any(company in text for company in major_companies):
            score += 2

        # Large funding amounts (+2)
        if any(amount in text for amount in ["$100m", "$100 m", "100 million", "$1b", "billion"]):
            score += 2
        elif any(amount in text for amount in ["$50m", "$50 m", "50 million"]):
            score += 1

        # Product launch keywords (+2)
        launch_keywords = [
            "launches",
            "unveils",
            "releases",
            "announces new",
            "debuts",
            "introduces",
        ]
        if any(keyword in text for keyword in launch_keywords):
            score += 2

        # Breakthrough/impact keywords (+1)
        impact_keywords = [
            "breakthrough",
            "first",
            "largest",
            "biggest",
            "revolutionary",
            "game-changing",
            "milestone",
        ]
        if any(keyword in text for keyword in impact_keywords):
            score += 1

        # AI-specific topics (+1)
        ai_keywords = [
            "llm",
            "large language model",
            "gpt",
            "claude",
            "chatbot",
            "generative ai",
            "machine learning",
            "deep learning",
            "neural network",
            "transformer",
        ]
        if any(keyword in text for keyword in ai_keywords):
            score += 1

        # Penalize opinion pieces (-1)
        if any(word in text for word in ["opinion", "commentary", "editorial"]):
            score -= 1

        # Ensure score is within 1-10
        score = max(1, min(10, score))

        return score
