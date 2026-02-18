"""
Integration tests for full content pipeline.
Tests end-to-end flow with real components.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.content_pipeline import ContentPipeline
from src.core.orchestrator import Orchestrator
from src.core.state_manager import StateManager
from src.models.newsletter import Newsletter
from src.publishing.base import PublishResult
from src.publishing.markdown_publisher import MarkdownPublisher
from src.research.arxiv_researcher import ArXivResearcher
from src.research.base import ContentItem


@pytest.fixture
async def temp_database():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = Path(f.name)

    state_manager = StateManager(db_path=db_path)
    await state_manager.init_db()

    yield state_manager

    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def temp_newsletters_dir():
    """Create temporary newsletters directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_research_items():
    """Create sample research items."""
    now = datetime.now()
    return [
        ContentItem(
            title="Novel Transformer Architecture for Efficient Training",
            url="https://arxiv.org/abs/2024.12345",
            source="arxiv",
            category="research",
            relevance_score=9,
            summary="This paper presents a breakthrough in transformer architectures that reduces training time by 50% while maintaining performance.",
            published_date=now,
            metadata={"authors": ["Smith, J.", "Doe, A."]},
        ),
        ContentItem(
            title="Multimodal Learning with Vision-Language Models",
            url="https://arxiv.org/abs/2024.54321",
            source="arxiv",
            category="research",
            relevance_score=8,
            summary="We introduce a novel approach to vision-language learning that achieves state-of-the-art results on multiple benchmarks.",
            published_date=now,
            metadata={"authors": ["Chen, L."]},
        ),
        ContentItem(
            title="Low Relevance Theoretical Proof",
            url="https://arxiv.org/abs/2024.99999",
            source="arxiv",
            category="research",
            relevance_score=3,  # Will be filtered out
            summary="A theoretical proof of convergence.",
            published_date=now,
            metadata={"authors": ["Theorist, T."]},
        ),
    ]


class TestArxivToNewsletter:
    """Test ArXiv research to newsletter flow."""

    @pytest.mark.asyncio
    async def test_arxiv_to_newsletter_flow(self, temp_database, sample_research_items):
        """Test converting ArXiv items through pipeline to newsletter."""
        pipeline = ContentPipeline(temp_database)

        # Process through pipeline
        newsletter_date = datetime.now().strftime("%Y-%m-%d-%H")
        newsletter = await pipeline.process(sample_research_items, newsletter_date)

        # Verify newsletter structure
        assert newsletter.date == newsletter_date
        assert newsletter.item_count == 2  # One filtered out due to low score
        assert len(newsletter.items) == 2
        assert newsletter.summary  # Should have a summary

        # Verify items
        for item in newsletter.items:
            assert item.relevance_score >= 5  # MIN_RELEVANCE_SCORE
            assert item.title
            assert item.url
            assert item.source == "arxiv"


class TestNewsletterToMarkdown:
    """Test newsletter to markdown publishing flow."""

    @pytest.mark.asyncio
    async def test_newsletter_to_markdown_publish(self, temp_newsletters_dir):
        """Test publishing newsletter to markdown file."""
        from src.models.newsletter import NewsletterItem

        # Create newsletter
        newsletter = Newsletter(
            date="2026-02-15-10",
            items=[
                NewsletterItem(
                    title="Test Paper",
                    url="https://arxiv.org/abs/2024.12345",
                    source="arxiv",
                    category="research",
                    relevance_score=8,
                    summary="Test summary",
                    published_date=datetime.now(),
                    metadata={},
                ),
            ],
            summary="Today's AI highlights include significant research.",
            item_count=1,
        )

        # Create publisher with temp directory
        with patch("src.config.settings.settings") as mock_settings:
            mock_settings.newsletters_dir = temp_newsletters_dir

            publisher = MarkdownPublisher()
            publisher.output_dir = temp_newsletters_dir

            result = await publisher.publish_newsletter(newsletter)

            # Verify publish succeeded
            assert result.success is True

            # Verify file was created
            expected_file = temp_newsletters_dir / "2026-02-15-10.md"
            assert expected_file.exists()

            # Verify content
            content = expected_file.read_text()
            assert "Test Paper" in content
            assert "Today's AI highlights" in content


class TestEndToEndCycle:
    """Test complete end-to-end cycle."""

    @pytest.mark.asyncio
    async def test_end_to_end_cycle(self, temp_database, temp_newsletters_dir):
        """Test full cycle from research to publish to database."""
        # Mock ArXiv researcher
        mock_researcher = MagicMock(spec=ArXivResearcher)
        mock_researcher.source_name = "arxiv"
        mock_researcher.research = AsyncMock(
            return_value=[
                ContentItem(
                    title="Breakthrough in LLM Training",
                    url="https://arxiv.org/abs/2024.11111",
                    source="arxiv",
                    category="research",
                    relevance_score=9,
                    summary="Revolutionary approach to training large language models.",
                    published_date=datetime.now(),
                    metadata={},
                ),
                ContentItem(
                    title="Novel Vision Transformer",
                    url="https://arxiv.org/abs/2024.22222",
                    source="arxiv",
                    category="research",
                    relevance_score=8,
                    summary="Efficient vision transformer for edge devices.",
                    published_date=datetime.now(),
                    metadata={},
                ),
            ]
        )

        # Create markdown publisher with temp directory
        with patch("src.config.settings.settings") as mock_settings:
            mock_settings.newsletters_dir = temp_newsletters_dir

            publisher = MarkdownPublisher()
            publisher.output_dir = temp_newsletters_dir

            # Create pipeline
            pipeline = ContentPipeline(temp_database)

            # Create orchestrator
            orchestrator = Orchestrator(
                state_manager=temp_database,
                researchers=[mock_researcher],
                publishers=[publisher],
                pipeline=pipeline,
            )

            # Run production cycle
            result = await orchestrator.run_cycle(mode="production")

            # Verify cycle succeeded
            assert result.success is True
            assert result.newsletter is not None
            assert result.item_count == 2
            assert result.filtered_count == 2

            # Verify publishing succeeded
            assert len(result.publish_results) == 1
            assert result.publish_results[0].success is True

            # Verify markdown file was created
            files = list(temp_newsletters_dir.glob("*.md"))
            assert len(files) == 1

            # Verify database records
            # Check newsletter record exists
            import aiosqlite

            async with aiosqlite.connect(temp_database.db_path) as db:
                cursor = await db.execute("SELECT * FROM newsletters")
                newsletters = await cursor.fetchall()
                assert len(newsletters) == 1

                # Check items were stored
                cursor = await db.execute("SELECT * FROM published_items")
                items = await cursor.fetchall()
                assert len(items) == 2

                # Check publishing log
                cursor = await db.execute("SELECT * FROM publishing_logs")
                logs = await cursor.fetchall()
                assert len(logs) == 1

    @pytest.mark.asyncio
    async def test_test_mode_no_publish(self, temp_database, temp_newsletters_dir):
        """Test that test mode doesn't publish or record."""
        # Mock researcher
        mock_researcher = MagicMock()
        mock_researcher.source_name = "arxiv"
        mock_researcher.research = AsyncMock(
            return_value=[
                ContentItem(
                    title="Test Paper",
                    url="https://arxiv.org/abs/2024.99999",
                    source="arxiv",
                    category="research",
                    relevance_score=8,
                    summary="Test",
                    published_date=datetime.now(),
                ),
            ]
        )

        # Create markdown publisher
        with patch("src.config.settings.settings") as mock_settings:
            mock_settings.newsletters_dir = temp_newsletters_dir

            publisher = MarkdownPublisher()
            publisher.output_dir = temp_newsletters_dir

            # Create orchestrator
            pipeline = ContentPipeline(temp_database)
            orchestrator = Orchestrator(
                state_manager=temp_database,
                researchers=[mock_researcher],
                publishers=[publisher],
                pipeline=pipeline,
            )

            # Run test cycle
            result = await orchestrator.run_cycle(mode="test")

            # Verify no publishing
            assert len(result.publish_results) == 0

            # Verify no markdown files
            files = list(temp_newsletters_dir.glob("*.md"))
            assert len(files) == 0

            # Verify no database records
            import aiosqlite

            async with aiosqlite.connect(temp_database.db_path) as db:
                cursor = await db.execute("SELECT * FROM newsletters")
                newsletters = await cursor.fetchall()
                assert len(newsletters) == 0


class TestPartialFailures:
    """Test handling of partial failures."""

    @pytest.mark.asyncio
    async def test_partial_publish_failure(self, temp_database):
        """Test that cycle continues if some publishers fail."""
        # Mock researchers
        mock_researcher = MagicMock()
        mock_researcher.source_name = "arxiv"
        mock_researcher.research = AsyncMock(
            return_value=[
                ContentItem(
                    title="Test",
                    url="https://example.com/1",
                    source="arxiv",
                    category="research",
                    relevance_score=8,
                    summary="Test",
                    published_date=datetime.now(),
                ),
            ]
        )

        # Create publishers (one will fail)
        success_publisher = MagicMock()
        success_publisher.platform_name = "markdown"
        success_publisher.publish_newsletter = AsyncMock(
            return_value=PublishResult(platform="markdown", success=True, message="OK")
        )

        fail_publisher = MagicMock()
        fail_publisher.platform_name = "discord"
        fail_publisher.publish_newsletter = AsyncMock(
            return_value=PublishResult(platform="discord", success=False, error="Webhook error")
        )

        # Create orchestrator
        pipeline = ContentPipeline(temp_database)
        orchestrator = Orchestrator(
            state_manager=temp_database,
            researchers=[mock_researcher],
            publishers=[success_publisher, fail_publisher],
            pipeline=pipeline,
        )
        orchestrator.enhancer = None  # enhancement not under test here

        # Run cycle
        result = await orchestrator.run_cycle(mode="production")

        # Should succeed overall
        assert result.success is True

        # Should have both results
        assert len(result.publish_results) == 2

        # Should have recorded (at least one platform succeeded)
        import aiosqlite

        async with aiosqlite.connect(temp_database.db_path) as db:
            cursor = await db.execute("SELECT * FROM newsletters")
            newsletters = await cursor.fetchall()
            assert len(newsletters) == 1
