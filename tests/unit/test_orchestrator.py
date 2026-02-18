"""
Unit tests for Orchestrator.
Tests phase coordination and error handling.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.orchestrator import CycleResult, Orchestrator
from src.models.newsletter import Newsletter, NewsletterItem
from src.publishing.base import PublishResult
from src.research.base import ContentItem


@pytest.fixture
def mock_state_manager():
    """Create mock StateManager."""
    manager = MagicMock()
    manager.init_db = AsyncMock()
    manager.create_newsletter_record = AsyncMock(return_value=123)
    manager.store_content = AsyncMock()
    manager.log_publishing_attempt = AsyncMock()
    manager.get_metrics = AsyncMock(return_value={"total_cost": 0.015})
    manager.track_api_usage = AsyncMock()
    return manager


@pytest.fixture
def mock_researchers():
    """Create mock researchers."""
    researcher1 = MagicMock()
    researcher1.source_name = "arxiv"
    researcher1.research = AsyncMock(
        return_value=[
            ContentItem(
                title="Paper 1",
                url="https://arxiv.org/1",
                source="arxiv",
                category="research",
                relevance_score=8,
                summary="Test 1",
            ),
            ContentItem(
                title="Paper 2",
                url="https://arxiv.org/2",
                source="arxiv",
                category="research",
                relevance_score=7,
                summary="Test 2",
            ),
        ]
    )

    researcher2 = MagicMock()
    researcher2.source_name = "huggingface"
    researcher2.research = AsyncMock(
        return_value=[
            ContentItem(
                title="Model Release",
                url="https://huggingface.co/1",
                source="huggingface",
                category="product",
                relevance_score=9,
                summary="New model",
            ),
        ]
    )

    return [researcher1, researcher2]


@pytest.fixture
def mock_publishers():
    """Create mock publishers."""
    discord_pub = MagicMock()
    discord_pub.platform_name = "discord"
    discord_pub.publish_newsletter = AsyncMock(
        return_value=PublishResult(
            platform="discord", success=True, message="Published successfully"
        )
    )
    discord_pub.publish_enhanced = AsyncMock(
        return_value=PublishResult(
            platform="discord", success=True, message="Published successfully"
        )
    )

    markdown_pub = MagicMock()
    markdown_pub.platform_name = "markdown"
    markdown_pub.publish_newsletter = AsyncMock(
        return_value=PublishResult(platform="markdown", success=True, message="File written")
    )
    markdown_pub.publish_enhanced = AsyncMock(
        return_value=PublishResult(platform="markdown", success=True, message="File written")
    )

    return [discord_pub, markdown_pub]


@pytest.fixture
def mock_pipeline():
    """Create mock ContentPipeline."""
    pipeline = MagicMock()
    pipeline.process = AsyncMock(
        return_value=Newsletter(
            date="2026-02-15-10",
            items=[
                NewsletterItem(
                    title="Paper 1",
                    url="https://arxiv.org/1",
                    source="arxiv",
                    category="research",
                    relevance_score=8,
                    summary="Test 1",
                ),
            ],
            summary="Today's highlights include significant research.",
            item_count=1,
        )
    )
    return pipeline


@pytest.fixture
def orchestrator(mock_state_manager, mock_researchers, mock_publishers, mock_pipeline):
    """Create Orchestrator with mocked dependencies."""
    return Orchestrator(
        state_manager=mock_state_manager,
        researchers=mock_researchers,
        publishers=mock_publishers,
        pipeline=mock_pipeline,
    )


class TestResearchPhase:
    """Test research phase execution."""

    @pytest.mark.asyncio
    async def test_research_phase_parallel_execution(self, orchestrator, mock_researchers):
        """Test that researchers run in parallel."""
        items = await orchestrator.research_phase()

        # Should have items from both researchers
        assert len(items) == 3

        # Verify all researchers were called
        for researcher in mock_researchers:
            researcher.research.assert_called_once()

    @pytest.mark.asyncio
    async def test_research_phase_handles_failures(self, orchestrator, mock_researchers):
        """Test that research continues if one researcher fails."""
        # Make first researcher fail
        mock_researchers[0].research.side_effect = Exception("ArXiv down")

        items = await orchestrator.research_phase()

        # Should still have items from successful researcher
        assert len(items) == 1
        assert items[0].source == "huggingface"

    @pytest.mark.asyncio
    async def test_research_phase_empty_results(self, orchestrator, mock_researchers):
        """Test handling of empty research results."""
        # Both researchers return empty
        mock_researchers[0].research.return_value = []
        mock_researchers[1].research.return_value = []

        items = await orchestrator.research_phase()

        assert len(items) == 0


class TestFilterPhase:
    """Test filter phase execution."""

    @pytest.mark.asyncio
    async def test_filter_phase_calls_pipeline(self, orchestrator, mock_pipeline):
        """Test that filter phase delegates to pipeline."""
        items = [
            ContentItem(
                title="Test",
                url="https://example.com/1",
                source="arxiv",
                category="research",
                relevance_score=8,
                summary="Test",
            ),
        ]

        newsletter = await orchestrator.filter_phase(items)

        # Verify pipeline was called
        mock_pipeline.process.assert_called_once()

        # Verify newsletter structure
        assert newsletter.item_count >= 0
        assert newsletter.date  # Should have a date


class TestPublishPhase:
    """Test publish phase execution."""

    @pytest.mark.asyncio
    async def test_publish_phase_parallel_execution(self, orchestrator, mock_publishers):
        """Test that publishers run in parallel."""
        newsletter = Newsletter(date="2026-02-15-10", items=[], summary="Test", item_count=0)

        results = await orchestrator.publish_phase(newsletter)

        # Should have results from all publishers
        assert len(results) == 2

        # Verify all publishers were called
        for publisher in mock_publishers:
            publisher.publish_newsletter.assert_called_once_with(newsletter)

    @pytest.mark.asyncio
    async def test_publish_phase_partial_failure_ok(self, orchestrator, mock_publishers):
        """Test that partial publishing failures are handled."""
        newsletter = Newsletter(date="2026-02-15-10", items=[], summary="Test", item_count=0)

        # Make Discord fail
        mock_publishers[0].publish_newsletter.return_value = PublishResult(
            platform="discord", success=False, error="Webhook error"
        )

        results = await orchestrator.publish_phase(newsletter)

        # Should have results from both (one success, one failure)
        assert len(results) == 2
        assert results[0].success is False
        assert results[1].success is True

    @pytest.mark.asyncio
    async def test_publish_phase_handles_crashes(self, orchestrator, mock_publishers):
        """Test that publisher crashes are handled."""
        newsletter = Newsletter(date="2026-02-15-10", items=[], summary="Test", item_count=0)

        # Make Discord crash
        mock_publishers[0].publish_newsletter.side_effect = Exception("Network error")

        results = await orchestrator.publish_phase(newsletter)

        # Should convert exception to PublishResult
        assert len(results) == 2
        assert results[0].success is False
        assert results[0].error == "Network error"
        assert results[1].success is True

    @pytest.mark.asyncio
    async def test_publish_phase_no_publishers(self, mock_state_manager, mock_pipeline):
        """Test publishing with no publishers configured."""
        orchestrator = Orchestrator(
            state_manager=mock_state_manager,
            researchers=[],
            publishers=[],  # No publishers
            pipeline=mock_pipeline,
        )

        newsletter = Newsletter(date="2026-02-15-10", items=[], summary="Test", item_count=0)

        results = await orchestrator.publish_phase(newsletter)

        # Should return empty list
        assert results == []


class TestRecordPhase:
    """Test record phase execution."""

    @pytest.mark.asyncio
    async def test_record_phase_stores_items(self, orchestrator, mock_state_manager):
        """Test that newsletter and items are stored."""
        newsletter = Newsletter(
            date="2026-02-15-10",
            items=[
                NewsletterItem(
                    title="Paper 1",
                    url="https://arxiv.org/1",
                    source="arxiv",
                    category="research",
                    relevance_score=8,
                    summary="Test",
                ),
            ],
            summary="Test summary",
            item_count=1,
        )

        publish_results = [
            PublishResult(platform="discord", success=True),
            PublishResult(platform="markdown", success=True),
        ]

        await orchestrator.record_phase(newsletter, publish_results)

        # Verify newsletter record created
        mock_state_manager.create_newsletter_record.assert_called_once()

        # Verify items stored
        assert mock_state_manager.store_content.call_count == 1

        # Verify publishing attempts logged
        assert mock_state_manager.log_publishing_attempt.call_count == 2

    @pytest.mark.asyncio
    async def test_record_phase_continues_on_item_error(self, orchestrator, mock_state_manager):
        """Test that recording continues if one item fails."""
        newsletter = Newsletter(
            date="2026-02-15-10",
            items=[
                NewsletterItem(
                    title="Paper 1",
                    url="https://arxiv.org/1",
                    source="arxiv",
                    category="research",
                    relevance_score=8,
                    summary="Test",
                ),
                NewsletterItem(
                    title="Paper 2",
                    url="https://arxiv.org/2",
                    source="arxiv",
                    category="research",
                    relevance_score=7,
                    summary="Test",
                ),
            ],
            summary="Test",
            item_count=2,
        )

        # Make first item storage fail
        mock_state_manager.store_content.side_effect = [
            Exception("Database error"),
            None,  # Second succeeds
        ]

        publish_results = []

        # Should not crash
        await orchestrator.record_phase(newsletter, publish_results)

        # Should have attempted both
        assert mock_state_manager.store_content.call_count == 2

    @pytest.mark.asyncio
    async def test_record_phase_handles_failure(self, orchestrator, mock_state_manager):
        """Test that record phase doesn't crash on error."""
        newsletter = Newsletter(date="2026-02-15-10", items=[], summary="Test", item_count=0)

        # Make newsletter record creation fail
        mock_state_manager.create_newsletter_record.side_effect = Exception("DB error")

        # Should not crash
        await orchestrator.record_phase(newsletter, [])


class TestRunCycle:
    """Test full cycle execution."""

    @pytest.mark.asyncio
    async def test_run_cycle_test_mode(self, orchestrator, mock_publishers):
        """Test cycle in test mode (no publishing)."""
        result = await orchestrator.run_cycle(mode="test")

        # Should succeed
        assert result.success is True
        assert result.newsletter is not None

        # Should not publish
        assert len(result.publish_results) == 0
        for publisher in mock_publishers:
            publisher.publish_newsletter.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_cycle_production_mode(
        self, orchestrator, mock_publishers, mock_state_manager
    ):
        """Test cycle in production mode (full pipeline)."""
        result = await orchestrator.run_cycle(mode="production")

        # Should succeed
        assert result.success is True
        assert result.newsletter is not None

        # Should publish (via publish_enhanced since enhancement is enabled)
        assert len(result.publish_results) == 2
        for publisher in mock_publishers:
            publisher.publish_enhanced.assert_called_once()

        # Should record
        mock_state_manager.create_newsletter_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_cycle_no_items_found(self, orchestrator, mock_researchers):
        """Test cycle when no items are found."""
        # Make all researchers return empty
        for researcher in mock_researchers:
            researcher.research.return_value = []

        result = await orchestrator.run_cycle(mode="test")

        # Should succeed but with no newsletter
        assert result.success is True
        assert result.newsletter is None
        assert result.item_count == 0
        assert result.error == "No items found"

    @pytest.mark.asyncio
    async def test_run_cycle_handles_errors(self, orchestrator, mock_researchers):
        """Test that cycle handles errors gracefully."""
        # Make research crash (but research_phase handles exceptions)
        for researcher in mock_researchers:
            researcher.research.side_effect = Exception("Critical error")

        result = await orchestrator.run_cycle(mode="test")

        # Should succeed but with no items (research failures are logged, not fatal)
        assert result.success is True
        assert result.item_count == 0
        assert result.error == "No items found"

    @pytest.mark.asyncio
    async def test_run_cycle_skips_record_if_all_publish_fail(
        self, orchestrator, mock_publishers, mock_state_manager
    ):
        """Test that recording is skipped if all platforms fail."""
        # Make all publishers fail (via publish_enhanced since enhancement is enabled)
        for publisher in mock_publishers:
            publisher.publish_enhanced.return_value = PublishResult(
                platform=publisher.platform_name, success=False, error="Failed"
            )

        await orchestrator.run_cycle(mode="production")

        # Should not record
        mock_state_manager.create_newsletter_record.assert_not_called()


class TestCycleResult:
    """Test CycleResult dataclass."""

    def test_platforms_published_property(self):
        """Test platforms_published property."""
        result = CycleResult(
            success=True,
            newsletter=None,
            item_count=5,
            filtered_count=3,
            publish_results=[
                PublishResult(platform="discord", success=True),
                PublishResult(platform="twitter", success=False),
                PublishResult(platform="markdown", success=True),
            ],
            total_cost=0.02,
        )

        # Should only include successful platforms
        assert result.platforms_published == ["discord", "markdown"]
