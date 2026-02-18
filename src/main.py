#!/usr/bin/env python3
"""
ElvAgent - AI Newsletter Agent
Main entry point for the application.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import settings
from src.core import ContentPipeline, Orchestrator, StateManager
from src.publishing.discord_publisher import DiscordPublisher
from src.publishing.markdown_publisher import MarkdownPublisher
from src.publishing.telegram_publisher import TelegramPublisher
from src.publishing.twitter_publisher import TwitterPublisher
from src.research.arxiv_researcher import ArXivResearcher
from src.research.huggingface_researcher import HuggingFaceResearcher
from src.research.reddit_researcher import RedditResearcher
from src.research.techcrunch_researcher import TechCrunchResearcher
from src.utils.logger import configure_logging, get_logger

logger = get_logger("main")


async def run_test_cycle():
    """Run a single test cycle without publishing."""
    logger.info("test_cycle_start", mode="test")

    # Initialize database
    state_manager = StateManager()
    await state_manager.init_db()

    # Initialize components
    researchers = [
        ArXivResearcher(max_items=5),
        HuggingFaceResearcher(max_items=5),
        RedditResearcher(max_items=5),
        TechCrunchResearcher(max_items=5),
    ]
    publishers = []  # Empty in test mode (no publishing)
    pipeline = ContentPipeline(state_manager)

    # Create orchestrator
    orchestrator = Orchestrator(
        state_manager=state_manager,
        researchers=researchers,
        publishers=publishers,
        pipeline=pipeline,
    )

    # Run cycle
    result = await orchestrator.run_cycle(mode="test")

    # Display results
    if result.newsletter:
        logger.info(
            "test_cycle_complete",
            mode="test",
            items_found=result.item_count,
            items_filtered=result.filtered_count,
            cost=f"${result.total_cost:.4f}",
        )

        # Display newsletter summary
        print("\n" + "=" * 60)
        print("NEWSLETTER PREVIEW")
        print("=" * 60)
        print(f"Date: {result.newsletter.date}")
        print(f"Items: {result.newsletter.item_count}")
        print(f"\nSummary:\n{result.newsletter.summary}")
        print("\nItems:")
        for i, item in enumerate(result.newsletter.items, 1):
            print(f"\n{i}. {item.title}")
            print(
                f"   Source: {item.source} | Category: {item.category} | Score: {item.relevance_score}"
            )
            print(f"   URL: {item.url}")
            print(f"   {item.summary[:100]}...")
        print("\n" + "=" * 60)
    else:
        logger.info("test_cycle_complete", mode="test", result="No items found")


async def run_production_cycle():
    """Run a full production cycle with publishing."""
    logger.info("production_cycle_start", mode="production")

    # Validate production configuration
    if not settings.validate_production_config():
        logger.error("production_config_invalid", skipping_cycle=True)
        return

    # Initialize database
    state_manager = StateManager()
    await state_manager.init_db()

    # Initialize components
    researchers = [
        ArXivResearcher(max_items=5),
        HuggingFaceResearcher(max_items=5),
        RedditResearcher(max_items=5),
        TechCrunchResearcher(max_items=5),
    ]
    publishers = [TelegramPublisher(), TwitterPublisher(), DiscordPublisher(), MarkdownPublisher()]
    pipeline = ContentPipeline(state_manager)

    # Create orchestrator
    orchestrator = Orchestrator(
        state_manager=state_manager,
        researchers=researchers,
        publishers=publishers,
        pipeline=pipeline,
    )

    # Run cycle
    result = await orchestrator.run_cycle(mode="production")

    # Log results
    if result.success:
        logger.info(
            "production_cycle_complete",
            mode="production",
            items_found=result.item_count,
            items_filtered=result.filtered_count,
            platforms_published=result.platforms_published,
            cost=f"${result.total_cost:.4f}",
        )
    else:
        logger.error("production_cycle_failed", error=result.error)


async def run_pa_mode():
    """Run ElvAgent as a fully autonomous Personal Assistant.

    Starts the MasterAgent which runs all sub-agents concurrently:
      - NewsletterAgent  : hourly AI news newsletter
      - GitHubMonitor    : PR description, CI fixing, code review
      - TaskWorker       : processes task queue (Phase B)
      - TelegramAgent    : bidirectional Telegram commands (Phase B)
    """
    from src.core.master_agent import MasterAgent

    master = MasterAgent()
    await master.run_forever()


async def run_github_monitor(max_cycles: int = 0):
    """Run the GitHub PR monitoring agent.

    Args:
        max_cycles: Maximum poll cycles (0 = run forever)
    """
    from src.github.client import GitHubClient
    from src.github.monitor import GitHubMonitor

    if not settings.github_token:
        logger.error("github_token_missing", hint="Set GITHUB_TOKEN in .env")
        return

    state_manager = StateManager()
    await state_manager.init_db()

    client = GitHubClient(token=settings.github_token, repo=settings.github_repo)
    monitor = GitHubMonitor(state_manager=state_manager, github_client=client)

    await monitor.run_forever(
        interval_seconds=settings.github_poll_interval,
        max_cycles=max_cycles,
    )


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="ElvAgent - AI Newsletter Agent")
    parser.add_argument(
        "--mode",
        choices=["test", "production", "github-monitor", "pa"],
        default="test",
        help=(
            "Run mode: test (no publishing), production (full cycle), "
            "github-monitor (PR agent), or pa (full personal assistant)"
        ),
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--cycles",
        type=int,
        default=0,
        help="Max poll cycles for github-monitor (0 = run forever)",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = "DEBUG" if args.verbose else settings.log_level
    global logger
    logger = configure_logging(
        log_level=log_level,
        log_file=settings.logs_dir / "stdout.log" if args.mode == "production" else None,
        pretty_console=True,
    )

    logger.info("elvagent_starting", mode=args.mode, verbose=args.verbose, version="0.1.0")

    # Ensure directories exist
    settings.ensure_directories()

    try:
        if args.mode == "test":
            await run_test_cycle()
        elif args.mode == "github-monitor":
            await run_github_monitor(max_cycles=args.cycles)
        elif args.mode == "pa":
            await run_pa_mode()
        else:
            await run_production_cycle()

        logger.info("elvagent_complete", mode=args.mode)

    except KeyboardInterrupt:
        logger.info("elvagent_interrupted")
        sys.exit(0)

    except Exception as e:
        logger.error("elvagent_failed", error=str(e), error_type=type(e).__name__)
        raise


if __name__ == "__main__":
    asyncio.run(main())
