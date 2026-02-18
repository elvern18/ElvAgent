"""Unit tests for researcher implementations."""

import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.research.huggingface_researcher import HuggingFaceResearcher
from src.research.reddit_researcher import RedditResearcher
from src.research.techcrunch_researcher import TechCrunchResearcher

# --- Fixtures ---


def _make_hf_paper(
    title="Test Paper",
    paper_id="2401.00001",
    abstract="A test abstract",
    num_comments=0,
    published_at=None,
):
    """Build a mock HuggingFace API paper object."""
    if published_at is None:
        published_at = datetime.now().isoformat() + "Z"
    return {
        "paper": {
            "id": paper_id,
            "title": title,
            "abstract": abstract,
            "authors": [{"name": "Alice"}, {"name": "Bob"}],
        },
        "numComments": num_comments,
        "publishedAt": published_at,
    }


def _make_rss_entry(
    title="Test Entry",
    link="https://reddit.com/r/ML/1",
    author="user1",
    summary="A discussion",
    published_parsed=None,
):
    """Build a mock feedparser entry."""
    if published_parsed is None:
        published_parsed = time.localtime()
    entry = MagicMock()
    entry.get = lambda k, d=None: {
        "title": title,
        "link": link,
        "author": author,
        "summary": summary,
    }.get(k, d)
    entry.published_parsed = published_parsed
    return entry


def _make_tc_entry(
    title="TC Article",
    link="https://techcrunch.com/article",
    author="Writer",
    summary="Article summary",
    tags=None,
    published_parsed=None,
):
    """Build a mock feedparser entry for TechCrunch."""
    if published_parsed is None:
        published_parsed = time.localtime()
    entry = MagicMock()
    entry.get = lambda k, d=None: {
        "title": title,
        "link": link,
        "author": author,
        "summary": summary,
    }.get(k, d)

    def _make_tag(term):
        tag = MagicMock()
        tag.get = lambda k, d=None: term if k == "term" else d
        return tag

    entry.tags = [_make_tag(t) for t in (tags or [])]
    entry.published_parsed = published_parsed
    # Make 'tags' appear in entry for the `if "tags" in entry` check
    entry.__contains__ = lambda self, k: k in ("tags", "published_parsed")
    return entry


def _httpx_mock(response_data=None, content=None):
    """Return a patched httpx.AsyncClient that yields mock_response."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    if response_data is not None:
        mock_response.json = MagicMock(return_value=response_data)
    if content is not None:
        mock_response.content = content
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)
    return mock_client, mock_response


# === HuggingFaceResearcher Tests ===


@pytest.mark.unit
class TestHuggingFaceResearcher:
    def test_score_base(self):
        r = HuggingFaceResearcher()
        score = r.score_relevance(
            {"title": "Boring title", "summary": "Nothing special", "num_comments": 0}
        )
        assert score == 5

    def test_score_high_comments(self):
        r = HuggingFaceResearcher()
        assert r.score_relevance({"title": "Paper", "summary": "", "num_comments": 25}) >= 7

    def test_score_medium_comments(self):
        r = HuggingFaceResearcher()
        assert r.score_relevance({"title": "Paper", "summary": "", "num_comments": 15}) >= 6

    def test_score_high_impact_keywords(self):
        r = HuggingFaceResearcher()
        score = r.score_relevance(
            {"title": "New LLM reasoning approach", "summary": "", "num_comments": 0}
        )
        assert score >= 7  # base 5 + 2 high_impact

    def test_score_practical_keywords(self):
        r = HuggingFaceResearcher()
        score = r.score_relevance(
            {"title": "Code implementation released", "summary": "", "num_comments": 0}
        )
        assert score >= 6  # base 5 + 1 practical

    def test_score_novel_keywords(self):
        r = HuggingFaceResearcher()
        score = r.score_relevance(
            {"title": "Novel breakthrough approach", "summary": "", "num_comments": 0}
        )
        assert score >= 6

    def test_score_capped_at_10(self):
        r = HuggingFaceResearcher()
        score = r.score_relevance(
            {
                "title": "Novel LLM transformer code breakthrough outperform",
                "summary": "state-of-the-art model implementation",
                "num_comments": 50,
            }
        )
        assert score == 10

    def test_parse_paper(self):
        r = HuggingFaceResearcher()
        paper = _make_hf_paper(
            title="Great Paper", paper_id="2401.99999", abstract="Abstract text", num_comments=5
        )
        result = r._parse_paper(paper)
        assert result["title"] == "Great Paper"
        assert result["url"] == "https://huggingface.co/papers/2401.99999"
        assert result["authors"] == ["Alice", "Bob"]
        assert result["num_comments"] == 5

    def test_parse_paper_truncates_long_summary(self):
        r = HuggingFaceResearcher()
        paper = _make_hf_paper(abstract="x" * 600)
        result = r._parse_paper(paper)
        assert len(result["summary"]) == 500

    @pytest.mark.asyncio
    async def test_fetch_content_returns_items(self):
        r = HuggingFaceResearcher()
        papers = [
            _make_hf_paper(title="LLM transformer paper", num_comments=15),
            _make_hf_paper(title="Boring unrelated paper", paper_id="0002"),
        ]
        mock_client, mock_response = _httpx_mock(response_data=papers)
        with patch("httpx.AsyncClient", return_value=mock_client):
            items = await r.fetch_content()
        # The LLM paper should pass relevance threshold; the boring one is borderline
        assert len(items) >= 1
        assert items[0].source == "huggingface"

    @pytest.mark.asyncio
    async def test_fetch_content_skips_old_papers(self):
        r = HuggingFaceResearcher()
        old_date = (datetime.now() - timedelta(days=10)).isoformat() + "Z"
        papers = [_make_hf_paper(title="LLM paper", published_at=old_date)]
        mock_client, _ = _httpx_mock(response_data=papers)
        with patch("httpx.AsyncClient", return_value=mock_client):
            items = await r.fetch_content()
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_fetch_content_http_error(self):
        r = HuggingFaceResearcher()
        mock_client, mock_response = _httpx_mock(response_data=[])
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await r.fetch_content()


# === RedditResearcher Tests ===


@pytest.mark.unit
class TestRedditResearcher:
    def test_score_base(self):
        r = RedditResearcher()
        assert r.score_relevance({"title": "Boring", "summary": "", "flair": ""}) == 5

    def test_score_research_flair(self):
        r = RedditResearcher()
        assert r.score_relevance({"title": "A paper", "summary": "", "flair": "R"}) >= 7

    def test_score_project_flair(self):
        r = RedditResearcher()
        assert r.score_relevance({"title": "My project", "summary": "", "flair": "P"}) >= 7

    def test_score_news_flair(self):
        r = RedditResearcher()
        assert r.score_relevance({"title": "News item", "summary": "", "flair": "N"}) >= 6

    def test_score_meme_penalty(self):
        r = RedditResearcher()
        score = r.score_relevance({"title": "Funny meme lol", "summary": "", "flair": ""})
        assert score <= 2

    def test_score_career_penalty(self):
        r = RedditResearcher()
        score = r.score_relevance({"title": "Career salary advice", "summary": "", "flair": ""})
        assert score <= 4

    def test_score_high_impact(self):
        r = RedditResearcher()
        score = r.score_relevance({"title": "Claude breakthrough", "summary": "", "flair": "R"})
        assert score >= 9

    def test_get_category_from_flair(self):
        r = RedditResearcher()
        assert r._get_category_from_flair("R") == "research"
        assert r._get_category_from_flair("D") == "news"
        assert r._get_category_from_flair("P") == "product"
        assert r._get_category_from_flair("N") == "news"
        assert r._get_category_from_flair("X") == "news"

    def test_parse_entry_strips_flair(self):
        r = RedditResearcher()
        entry = _make_rss_entry(title="[R] A New Transformer Model")
        result = r._parse_entry(entry)
        assert result["flair"] == "R"
        assert result["title"] == "A New Transformer Model"

    def test_parse_entry_no_flair(self):
        r = RedditResearcher()
        entry = _make_rss_entry(title="Just a plain title")
        result = r._parse_entry(entry)
        assert result["flair"] == ""
        assert result["title"] == "Just a plain title"

    def test_parse_entry_strips_html(self):
        r = RedditResearcher()
        entry = _make_rss_entry(summary="<p>Hello <b>world</b></p>")
        result = r._parse_entry(entry)
        assert "<" not in result["summary"]

    @pytest.mark.asyncio
    async def test_fetch_content_returns_items(self):
        r = RedditResearcher()
        mock_client, mock_response = _httpx_mock(content=b"<rss/>")
        mock_feed = MagicMock()
        mock_feed.entries = [
            _make_rss_entry(title="[R] LLM transformer breakthrough"),
        ]
        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("src.research.reddit_researcher.feedparser.parse", return_value=mock_feed),
        ):
            items = await r.fetch_content()
        assert len(items) >= 1
        assert items[0].source == "reddit"

    @pytest.mark.asyncio
    async def test_fetch_content_filters_memes(self):
        r = RedditResearcher()
        mock_client, mock_response = _httpx_mock(content=b"<rss/>")
        mock_feed = MagicMock()
        mock_feed.entries = [
            _make_rss_entry(title="Funny meme joke lol"),
        ]
        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("src.research.reddit_researcher.feedparser.parse", return_value=mock_feed),
        ):
            items = await r.fetch_content()
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_fetch_content_http_error(self):
        r = RedditResearcher()
        mock_client, mock_response = _httpx_mock(content=b"")
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await r.fetch_content()


# === TechCrunchResearcher Tests ===


@pytest.mark.unit
class TestTechCrunchResearcher:
    def test_score_base(self):
        r = TechCrunchResearcher()
        assert r.score_relevance({"title": "Random article", "summary": ""}) == 5

    def test_score_major_company(self):
        r = TechCrunchResearcher()
        score = r.score_relevance({"title": "OpenAI news", "summary": ""})
        assert score >= 7

    def test_score_large_funding(self):
        r = TechCrunchResearcher()
        score = r.score_relevance({"title": "Startup raises $100 million", "summary": ""})
        assert score >= 7

    def test_score_medium_funding(self):
        r = TechCrunchResearcher()
        score = r.score_relevance({"title": "Startup raises 50 million", "summary": ""})
        assert score >= 6

    def test_score_launch_keywords(self):
        r = TechCrunchResearcher()
        score = r.score_relevance({"title": "Company launches new product", "summary": ""})
        assert score >= 7

    def test_score_opinion_penalty(self):
        r = TechCrunchResearcher()
        score = r.score_relevance({"title": "Opinion editorial on AI", "summary": ""})
        assert score <= 5

    def test_score_combined_high(self):
        r = TechCrunchResearcher()
        score = r.score_relevance(
            {
                "title": "OpenAI launches new GPT model, a breakthrough milestone",
                "summary": "",
            }
        )
        assert score == 10

    def test_detect_category_funding(self):
        r = TechCrunchResearcher()
        assert r._detect_category({"title": "Startup raises $50M", "summary": ""}) == "funding"

    def test_detect_category_product(self):
        r = TechCrunchResearcher()
        assert (
            r._detect_category({"title": "Company launches new tool", "summary": ""}) == "product"
        )

    def test_detect_category_regulation(self):
        r = TechCrunchResearcher()
        assert (
            r._detect_category({"title": "New AI regulation policy", "summary": ""}) == "regulation"
        )

    def test_detect_category_default(self):
        r = TechCrunchResearcher()
        assert r._detect_category({"title": "Something else", "summary": ""}) == "news"

    def test_parse_entry_extracts_tags(self):
        r = TechCrunchResearcher()
        entry = _make_tc_entry(tags=["AI", "Startups"])
        result = r._parse_entry(entry)
        assert result["tags"] == ["AI", "Startups"]

    def test_parse_entry_strips_html(self):
        r = TechCrunchResearcher()
        entry = _make_tc_entry(summary="<p>Hello <a href='x'>link</a></p>")
        result = r._parse_entry(entry)
        assert "<" not in result["summary"]

    @pytest.mark.asyncio
    async def test_fetch_content_returns_items(self):
        r = TechCrunchResearcher()
        mock_client, _ = _httpx_mock(content=b"<rss/>")
        mock_feed = MagicMock()
        mock_feed.entries = [
            _make_tc_entry(title="OpenAI launches new GPT model"),
        ]
        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("src.research.techcrunch_researcher.feedparser.parse", return_value=mock_feed),
        ):
            items = await r.fetch_content()
        assert len(items) >= 1
        assert items[0].source == "techcrunch"

    @pytest.mark.asyncio
    async def test_fetch_content_http_error(self):
        r = TechCrunchResearcher()
        mock_client, mock_response = _httpx_mock(content=b"")
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=MagicMock()
        )
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await r.fetch_content()
