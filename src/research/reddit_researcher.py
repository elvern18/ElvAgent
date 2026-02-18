"""
Reddit researcher for fetching Machine Learning discussions.
Fetches from r/MachineLearning RSS feed and scores relevance.
"""

import re
from datetime import datetime
from typing import Any

import feedparser
import httpx

from src.research.base import BaseResearcher, ContentItem


class RedditResearcher(BaseResearcher):
    """Researcher for Reddit r/MachineLearning."""

    RSS_URL = "https://www.reddit.com/r/MachineLearning/hot.rss"

    def __init__(self, max_items: int = 5):
        """Initialize Reddit researcher."""
        super().__init__(source_name="reddit", max_items=max_items)

    async def fetch_content(self) -> list[ContentItem]:
        """
        Fetch and parse Reddit RSS feed.

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

                    # Skip if outside time window (use 24 hours for Reddit)
                    if not self.is_within_time_window(item_data["published_date"], hours=24):
                        continue

                    # Score relevance
                    relevance_score = self.score_relevance(item_data)

                    # Skip low-relevance items (filters out memes/jokes)
                    if relevance_score < 5:
                        continue

                    # Determine category from flair
                    category = self._get_category_from_flair(item_data.get("flair", ""))

                    # Create ContentItem
                    content_item = ContentItem(
                        title=item_data["title"],
                        url=self.normalize_url(item_data["url"]),
                        source=self.source_name,
                        category=category,
                        relevance_score=relevance_score,
                        summary=item_data["summary"],
                        metadata={
                            "flair": item_data.get("flair"),
                            "author": item_data.get("author"),
                            "subreddit": "r/MachineLearning",
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
        # Extract raw title
        raw_title = entry.get("title", "").strip()

        # Extract flair tag (e.g., [R], [D], [P], [N])
        flair = ""
        title = raw_title
        flair_match = re.match(r"\[([A-Z])\]\s*(.*)", raw_title)
        if flair_match:
            flair = flair_match.group(1)
            title = flair_match.group(2)

        # Extract URL
        url = entry.get("link", "")

        # Extract author
        author = entry.get("author", "unknown")

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
            "raw_title": raw_title,
            "flair": flair,
            "url": url,
            "author": author,
            "summary": summary,
            "published_date": published_date,
        }

    def _get_category_from_flair(self, flair: str) -> str:
        """
        Determine category from Reddit flair tag.

        Args:
            flair: Flair tag (R, D, P, N, etc.)

        Returns:
            Category string
        """
        flair_map = {
            "R": "research",  # Research paper
            "D": "news",  # Discussion
            "P": "product",  # Project
            "N": "news",  # News
        }
        return flair_map.get(flair, "news")

    def score_relevance(self, item: dict[str, Any]) -> int:
        """
        Score relevance from 1-10.

        Prioritizes:
        - Research papers and discussions
        - Breakthrough/SOTA mentions
        - High engagement topics
        - Filters out memes/jokes

        Args:
            item: Parsed item dictionary

        Returns:
            Relevance score (1-10)
        """
        score = 5  # Base score

        title = item["title"].lower()
        summary = item["summary"].lower()
        text = f"{title} {summary}"
        flair = item.get("flair", "")

        # Flair-based scoring (+2)
        if flair in ["R", "D"]:  # Research or Discussion
            score += 2
        elif flair == "P":  # Project
            score += 2
        elif flair == "N":  # News
            score += 1

        # High-impact keywords (+2)
        high_impact = [
            "llm",
            "large language model",
            "breakthrough",
            "sota",
            "state-of-the-art",
            "gpt",
            "claude",
            "multimodal",
            "diffusion",
            "transformer",
        ]
        if any(keyword in text for keyword in high_impact):
            score += 2

        # Novel/impressive keywords (+1)
        novel = [
            "novel",
            "outperform",
            "surpass",
            "efficient",
            "release",
            "open-source",
            "benchmark",
        ]
        if any(keyword in text for keyword in novel):
            score += 1

        # Practical/code keywords (+1)
        practical = ["code", "implementation", "github", "paper", "model", "dataset", "tool"]
        if any(keyword in text for keyword in practical):
            score += 1

        # Penalize memes and jokes (-3, effectively filters them out)
        meme_keywords = ["meme", "joke", "funny", "humor", "lol", "shitpost", "rant", "confession"]
        if any(keyword in text for keyword in meme_keywords):
            score -= 3

        # Penalize off-topic content (-1)
        if any(word in text for word in ["career", "salary", "interview", "resume"]):
            score -= 1

        # Ensure score is within 1-10
        score = max(1, min(10, score))

        return score
