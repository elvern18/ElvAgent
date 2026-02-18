"""
HuggingFace researcher for fetching daily papers.
Fetches from HuggingFace daily papers API and scores relevance.
"""

from datetime import datetime
from typing import Any

import httpx

from src.research.base import BaseResearcher, ContentItem


class HuggingFaceResearcher(BaseResearcher):
    """Researcher for HuggingFace daily papers."""

    API_URL = "https://huggingface.co/api/daily_papers"

    def __init__(self, max_items: int = 5):
        """Initialize HuggingFace researcher."""
        super().__init__(source_name="huggingface", max_items=max_items)

    async def fetch_content(self) -> list[ContentItem]:
        """
        Fetch and parse HuggingFace daily papers API.

        Returns:
            List of ContentItem objects
        """
        items = []

        try:
            # Fetch JSON API
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.API_URL)
                response.raise_for_status()

            # Parse JSON
            papers = response.json()

            self.logger.info("api_parsed", source=self.source_name, paper_count=len(papers))

            for paper in papers:
                try:
                    # Parse paper
                    item_data = self._parse_paper(paper)

                    # Skip if outside time window (use 7 days for HuggingFace daily papers)
                    if not self.is_within_time_window(item_data["published_date"], hours=168):
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
                            "num_comments": item_data.get("num_comments", 0),
                            "paper_id": item_data.get("paper_id"),
                            "arxiv_id": item_data.get("arxiv_id"),
                        },
                        published_date=item_data["published_date"],
                    )

                    items.append(content_item)

                except Exception as e:
                    self.logger.warning(
                        "paper_parse_failed",
                        error=str(e),
                        paper_title=paper.get("title", "unknown"),
                    )
                    continue

        except Exception as e:
            self.logger.error("api_fetch_failed", source=self.source_name, error=str(e))
            raise

        return items

    def _parse_paper(self, paper: dict[str, Any]) -> dict[str, Any]:
        """
        Parse API response into structured data.

        Args:
            paper: Paper object from API

        Returns:
            Dictionary with parsed data
        """
        # Extract paper details
        paper_data = paper.get("paper", {})

        # Extract title
        title = paper_data.get("title", "").strip()

        # Extract paper ID and build URL
        paper_id = paper_data.get("id", "")
        url = f"https://huggingface.co/papers/{paper_id}" if paper_id else ""

        # Extract ArXiv ID if available
        arxiv_id = paper_id if paper_id.startswith("arxiv:") else ""

        # Extract authors
        authors = []
        if "authors" in paper_data:
            authors = [author.get("name", "") for author in paper_data.get("authors", [])]

        # Extract summary (try both abstract and top-level summary)
        summary = paper_data.get("abstract", "") or paper.get("summary", "")
        summary = summary.strip()

        # Truncate summary if too long
        if len(summary) > 500:
            summary = summary[:497] + "..."

        # Extract comment count (proxy for community interest)
        num_comments = paper.get("numComments", 0)

        # Published date - HuggingFace shows daily papers, so use current date
        # Parse publishedAt if available
        published_date = datetime.now()
        if "publishedAt" in paper:
            try:
                # Parse and convert to timezone-naive for consistency
                published_date = datetime.fromisoformat(
                    paper["publishedAt"].replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except Exception:
                pass

        return {
            "title": title,
            "url": url,
            "paper_id": paper_id,
            "arxiv_id": arxiv_id,
            "authors": authors,
            "summary": summary,
            "num_comments": num_comments,
            "published_date": published_date,
        }

    def score_relevance(self, item: dict[str, Any]) -> int:
        """
        Score relevance from 1-10.

        Prioritizes:
        - High comment count (community interest)
        - Multimodal/LLM topics
        - Code implementations
        - Novel approaches

        Args:
            item: Parsed item dictionary

        Returns:
            Relevance score (1-10)
        """
        score = 5  # Base score

        title = item["title"].lower()
        summary = item["summary"].lower()
        text = f"{title} {summary}"
        num_comments = item.get("num_comments", 0)

        # High comment count indicates community interest (+2)
        if num_comments > 20:
            score += 2
        elif num_comments > 10:
            score += 1

        # High-impact keywords (+2)
        high_impact = [
            "llm",
            "large language model",
            "multimodal",
            "diffusion",
            "agent",
            "reasoning",
            "vision-language",
            "gpt",
            "transformer",
            "attention",
        ]
        if any(keyword in text for keyword in high_impact):
            score += 2

        # Implementation/code keywords (+1)
        practical = ["code", "implementation", "github", "model", "training", "fine-tuning"]
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
            "efficient",
        ]
        if any(keyword in text for keyword in novel):
            score += 1

        # Ensure score is within 1-10
        score = max(1, min(10, score))

        return score
