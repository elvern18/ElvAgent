#!/usr/bin/env python3
"""
ElvAgent - AI Newsletter Agent
Main entry point for the application.
"""
import asyncio
import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import settings
from src.utils.logger import configure_logging, get_logger


async def run_test_cycle():
    """Run a single test cycle without publishing."""
    logger.info("test_cycle_start", mode="test")

    # TODO: Implement test cycle
    # 1. Research phase
    # 2. Filter and rank
    # 3. Generate newsletter (don't publish)
    # 4. Display results

    logger.info("test_cycle_complete", mode="test")


async def run_production_cycle():
    """Run a full production cycle with publishing."""
    logger.info("production_cycle_start", mode="production")

    # TODO: Implement full cycle
    # 1. Research phase
    # 2. Filter and rank
    # 3. Generate newsletter
    # 4. Publish to all platforms
    # 5. Update database

    logger.info("production_cycle_complete", mode="production")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="ElvAgent - AI Newsletter Agent")
    parser.add_argument(
        "--mode",
        choices=["test", "production"],
        default="test",
        help="Run mode: test (no publishing) or production (full cycle)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    log_level = "DEBUG" if args.verbose else settings.log_level
    global logger
    logger = configure_logging(
        log_level=log_level,
        log_file=settings.logs_dir / "stdout.log" if args.mode == "production" else None,
        pretty_console=True
    )

    logger.info(
        "elvagent_starting",
        mode=args.mode,
        verbose=args.verbose,
        version="0.1.0"
    )

    # Ensure directories exist
    settings.ensure_directories()

    try:
        if args.mode == "test":
            await run_test_cycle()
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
