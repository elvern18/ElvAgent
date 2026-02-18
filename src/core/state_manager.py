"""
State management using SQLite database.
Handles content tracking, deduplication, metrics, and publishing logs.
"""

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import aiosqlite

from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("state_manager")


class StateManager:
    """Manage application state in SQLite database."""

    def __init__(self, db_path: Path | None = None):
        """
        Initialize state manager.

        Args:
            db_path: Path to SQLite database (defaults to settings.database_path)
        """
        self.db_path = db_path or settings.database_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init_db(self):
        """Initialize database schema."""
        logger.info("initializing_database", db_path=str(self.db_path))

        async with aiosqlite.connect(self.db_path) as db:
            # Published items table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS published_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_id TEXT UNIQUE NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT,
                    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    newsletter_date TEXT,
                    category TEXT,
                    metadata JSON
                )
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_content_id
                ON published_items(content_id)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_published_at
                ON published_items(published_at)
            """)

            # Newsletters table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS newsletters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    item_count INTEGER,
                    platforms_published JSON,
                    skip_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Publishing logs table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS publishing_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    newsletter_id INTEGER,
                    platform TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    attempt_count INTEGER DEFAULT 1,
                    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (newsletter_id) REFERENCES newsletters(id)
                )
            """)

            # API metrics table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS api_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    api_name TEXT NOT NULL,
                    request_count INTEGER DEFAULT 0,
                    token_count INTEGER DEFAULT 0,
                    estimated_cost REAL DEFAULT 0.0,
                    UNIQUE(date, api_name)
                )
            """)

            # Content fingerprints table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS content_fingerprints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_hash TEXT UNIQUE NOT NULL,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source TEXT
                )
            """)

            await db.commit()

        logger.info("database_initialized", db_path=str(self.db_path))

    @staticmethod
    def generate_content_id(url: str, title: str) -> str:
        """
        Generate unique content ID from URL and title.

        Args:
            url: Content URL
            title: Content title

        Returns:
            SHA-256 hash of normalized URL + title
        """
        # Normalize: lowercase, strip whitespace
        normalized = f"{url.strip().lower()}:{title.strip().lower()}"
        return hashlib.sha256(normalized.encode()).hexdigest()

    async def check_duplicate(self, url: str, title: str) -> bool:
        """
        Check if content already exists in database.

        Args:
            url: Content URL
            title: Content title

        Returns:
            True if duplicate exists, False otherwise
        """
        content_id = self.generate_content_id(url, title)

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM content_fingerprints WHERE content_hash = ?", (content_id,)
            )
            result = await cursor.fetchone()

        is_duplicate = result is not None

        if is_duplicate:
            logger.debug("duplicate_content_found", content_id=content_id, title=title)

        return is_duplicate

    async def store_fingerprint(self, url: str, title: str, source: str):
        """
        Store content fingerprint to prevent future duplicates.

        Args:
            url: Content URL
            title: Content title
            source: Content source (e.g., 'arxiv', 'huggingface')
        """
        content_hash = self.generate_content_id(url, title)

        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    """
                    INSERT INTO content_fingerprints (content_hash, source)
                    VALUES (?, ?)
                    """,
                    (content_hash, source),
                )
                await db.commit()
                logger.debug("fingerprint_stored", content_hash=content_hash, source=source)
            except aiosqlite.IntegrityError:
                # Already exists, ignore
                pass

    async def store_content(self, item: dict[str, Any]) -> int:
        """
        Store published content item.

        Args:
            item: Content item dictionary with keys:
                - url: Content URL
                - title: Content title
                - source: Source name
                - category: Content category
                - newsletter_date: Newsletter date string
                - metadata: Additional metadata (optional)

        Returns:
            ID of inserted row
        """
        content_id = self.generate_content_id(item["url"], item["title"])

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO published_items
                (content_id, source, title, url, newsletter_date, category, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    content_id,
                    item["source"],
                    item["title"],
                    item["url"],
                    item.get("newsletter_date"),
                    item.get("category"),
                    json.dumps(item.get("metadata", {})),
                ),
            )
            await db.commit()
            row_id = cursor.lastrowid

        # Also store fingerprint
        await self.store_fingerprint(item["url"], item["title"], item["source"])

        logger.info(
            "content_stored", content_id=content_id, title=item["title"], source=item["source"]
        )

        return row_id

    async def create_newsletter_record(
        self,
        newsletter_date: str,
        item_count: int,
        platforms_published: list[str],
        skip_reason: str | None = None,
    ) -> int:
        """
        Create newsletter record.

        Args:
            newsletter_date: Date string (YYYY-MM-DD-HH)
            item_count: Number of items in newsletter
            platforms_published: List of platforms published to
            skip_reason: Reason for skipping (if applicable)

        Returns:
            ID of inserted row
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO newsletters
                (date, item_count, platforms_published, skip_reason)
                VALUES (?, ?, ?, ?)
                """,
                (newsletter_date, item_count, json.dumps(platforms_published), skip_reason),
            )
            await db.commit()
            newsletter_id = cursor.lastrowid

        logger.info(
            "newsletter_record_created",
            newsletter_id=newsletter_id,
            date=newsletter_date,
            item_count=item_count,
        )

        return newsletter_id

    async def log_publishing_attempt(
        self,
        newsletter_id: int,
        platform: str,
        status: str,
        error_message: str | None = None,
        attempt_count: int = 1,
    ):
        """
        Log a publishing attempt.

        Args:
            newsletter_id: Newsletter ID
            platform: Platform name (e.g., 'discord', 'twitter')
            status: Status ('success', 'failed', 'retrying')
            error_message: Error message if failed
            attempt_count: Attempt number
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO publishing_logs
                (newsletter_id, platform, status, error_message, attempt_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (newsletter_id, platform, status, error_message, attempt_count),
            )
            await db.commit()

        logger.info(
            "publishing_logged",
            newsletter_id=newsletter_id,
            platform=platform,
            status=status,
            attempt=attempt_count,
        )

    async def track_api_usage(
        self,
        api_name: str,
        request_count: int = 1,
        token_count: int = 0,
        estimated_cost: float = 0.0,
    ):
        """
        Track API usage metrics.

        Args:
            api_name: API name (e.g., 'anthropic', 'openai')
            request_count: Number of requests
            token_count: Number of tokens used
            estimated_cost: Estimated cost in USD
        """
        today = str(date.today())

        async with aiosqlite.connect(self.db_path) as db:
            # Try to update existing record
            await db.execute(
                """
                INSERT INTO api_metrics (date, api_name, request_count, token_count, estimated_cost)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date, api_name) DO UPDATE SET
                    request_count = request_count + excluded.request_count,
                    token_count = token_count + excluded.token_count,
                    estimated_cost = estimated_cost + excluded.estimated_cost
                """,
                (today, api_name, request_count, token_count, estimated_cost),
            )
            await db.commit()

        logger.debug(
            "api_usage_tracked",
            api_name=api_name,
            requests=request_count,
            tokens=token_count,
            cost=f"${estimated_cost:.4f}",
        )

    async def get_metrics(self, target_date: str | None = None) -> dict[str, Any]:
        """
        Get API usage metrics for a specific date.

        Args:
            target_date: Date string (YYYY-MM-DD). Defaults to today.

        Returns:
            Dictionary of metrics by API
        """
        if target_date is None:
            target_date = str(date.today())

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT api_name, request_count, token_count, estimated_cost
                FROM api_metrics
                WHERE date = ?
                """,
                (target_date,),
            )
            rows = await cursor.fetchall()

        metrics = {}
        total_cost = 0.0

        for row in rows:
            api_name, requests, tokens, cost = row
            metrics[api_name] = {"requests": requests, "tokens": tokens, "cost": cost}
            total_cost += cost

        metrics["total_cost"] = total_cost

        return metrics
