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

            # GitHub agent events table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS github_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pr_number INTEGER NOT NULL,
                    head_sha TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    action_taken TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(pr_number, head_sha, event_type)
                )
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_github_events_pr ON github_events(pr_number)
            """)

            # PA task queue table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS task_queue (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type   TEXT NOT NULL,
                    payload     TEXT NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'pending',
                    priority    INTEGER NOT NULL DEFAULT 5,
                    chat_id     INTEGER,
                    result      TEXT,
                    error       TEXT,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_queue_status
                ON task_queue(status, priority, created_at)
            """)

            # PA agent facts table (persistent key/value memory)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS agent_facts (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    key        TEXT UNIQUE NOT NULL,
                    value      TEXT NOT NULL,
                    source     TEXT NOT NULL DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

        metrics: dict[str, Any] = {}
        total_cost = 0.0

        for row in rows:
            api_name, requests, tokens, cost = row
            metrics[api_name] = {"requests": requests, "tokens": tokens, "cost": cost}
            total_cost += cost

        metrics["total_cost"] = total_cost

        return metrics

    async def record_github_event(
        self,
        pr_number: int,
        head_sha: str,
        event_type: str,
        action_taken: str,
    ) -> None:
        """
        Record a processed GitHub PR event.

        Args:
            pr_number: Pull request number
            head_sha: Head commit SHA at time of processing
            event_type: Event type (e.g., 'needs_description', 'ci_failure', 'needs_review')
            action_taken: Action that was taken (e.g., 'description_generated', 'ruff_fix_pushed')
        """
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    """
                    INSERT INTO github_events (pr_number, head_sha, event_type, action_taken)
                    VALUES (?, ?, ?, ?)
                    """,
                    (pr_number, head_sha, event_type, action_taken),
                )
                await db.commit()
                logger.debug(
                    "github_event_recorded",
                    pr_number=pr_number,
                    event_type=event_type,
                    action_taken=action_taken,
                )
            except aiosqlite.IntegrityError:
                # Already recorded (UNIQUE constraint), ignore
                pass

    async def is_github_event_processed(
        self,
        pr_number: int,
        head_sha: str,
        event_type: str,
    ) -> bool:
        """
        Check if a GitHub PR event has already been processed.

        Args:
            pr_number: Pull request number
            head_sha: Head commit SHA
            event_type: Event type to check

        Returns:
            True if already processed, False otherwise
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT 1 FROM github_events
                WHERE pr_number = ? AND head_sha = ? AND event_type = ?
                """,
                (pr_number, head_sha, event_type),
            )
            result = await cursor.fetchone()
        return result is not None

    async def count_fix_attempts(self, pr_number: int) -> int:
        """
        Count the number of CI fix pushes for a given PR (circuit breaker).

        Args:
            pr_number: Pull request number

        Returns:
            Number of fix attempts (ruff_fix_pushed or ai_fix_pushed)
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT COUNT(*) FROM github_events
                WHERE pr_number = ?
                AND action_taken IN ('ruff_fix_pushed', 'ai_fix_pushed')
                """,
                (pr_number,),
            )
            result = await cursor.fetchone()
        return result[0] if result else 0

    async def get_fix_history(self, pr_number: int) -> list[dict]:
        """
        Return the chronological history of fix pushes for a PR.

        Used to give Claude context about what was already tried so it
        doesn't repeat the same fix.

        Args:
            pr_number: Pull request number

        Returns:
            List of dicts with keys: head_sha, action_taken, processed_at
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT head_sha, action_taken, processed_at
                FROM github_events
                WHERE pr_number = ?
                AND action_taken IN ('ruff_fix_pushed', 'ai_fix_pushed')
                ORDER BY processed_at ASC
                """,
                (pr_number,),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def minutes_since_last_newsletter(self) -> float:
        """
        Return minutes elapsed since the most recent newsletter was published.

        Used by NewsletterAgent to decide whether a new run is due.

        Returns:
            Minutes since last newsletter, or a large value (999_999) if none
            has ever been published (triggers first run immediately).
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT (julianday('now') - julianday(MAX(created_at))) * 24 * 60
                FROM newsletters
                """
            )
            row = await cursor.fetchone()

        if row is None or row[0] is None:
            return 999_999.0

        return float(row[0])

    # ------------------------------------------------------------------
    # PA memory helpers
    # ------------------------------------------------------------------

    async def set_fact(self, key: str, value: str, source: str = "user") -> None:
        """
        Upsert a persistent agent fact (key/value pair).

        Args:
            key: Unique fact key (e.g. 'default_repo')
            value: Fact value
            source: Who set it — 'user', 'agent', or 'system'
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO agent_facts (key, value, source, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    source = excluded.source,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value, source),
            )
            await db.commit()
        logger.debug("fact_set", key=key, source=source)

    async def get_fact(self, key: str) -> str | None:
        """
        Retrieve a persistent fact by key.

        Args:
            key: Fact key

        Returns:
            Fact value, or None if not found
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT value FROM agent_facts WHERE key = ?", (key,))
            row = await cursor.fetchone()
        return row[0] if row else None

    async def get_all_facts(self) -> dict[str, str]:
        """Return all agent facts as a key → value dict."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT key, value FROM agent_facts ORDER BY key")
            rows = await cursor.fetchall()
        return {row["key"]: row["value"] for row in rows}
