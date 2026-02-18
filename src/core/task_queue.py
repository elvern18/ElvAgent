"""
SQLite-backed priority task queue for the PA system.

Tasks are pushed by incoming sources (e.g. Telegram commands) and processed
by the TaskWorker agent. Priority 1 = highest, 10 = lowest.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("task_queue")

VALID_TASK_TYPES = frozenset({"code", "newsletter", "status", "shell"})
VALID_STATUSES = frozenset({"pending", "in_progress", "done", "failed"})


@dataclass
class Task:
    """A queued task."""

    task_type: str
    payload: dict[str, Any]
    id: int = 0
    status: str = "pending"
    priority: int = 5
    chat_id: int | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class TaskQueue:
    """
    Async SQLite-backed priority task queue.

    Push tasks from any source (Telegram, cron, API).
    Pop claims the next pending task and marks it in_progress atomically.
    Update records the outcome (done or failed).
    """

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.database_path

    async def push(
        self,
        task_type: str,
        payload: dict[str, Any],
        chat_id: int | None = None,
        priority: int = 5,
    ) -> int:
        """
        Add a task to the queue.

        Args:
            task_type: One of 'code', 'newsletter', 'status', 'shell'
            payload: Task-specific data (must be JSON-serialisable)
            chat_id: Telegram chat ID to reply to on completion
            priority: 1 = highest, 10 = lowest

        Returns:
            Assigned task ID
        """
        if task_type not in VALID_TASK_TYPES:
            raise ValueError(f"Unknown task_type {task_type!r}. Valid: {VALID_TASK_TYPES}")

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO task_queue (task_type, payload, chat_id, priority)
                VALUES (?, ?, ?, ?)
                """,
                (task_type, json.dumps(payload), chat_id, priority),
            )
            await db.commit()
            task_id = cursor.lastrowid

        logger.info("task_queued", task_id=task_id, task_type=task_type, priority=priority)
        return task_id

    async def pop(self, task_type: str | None = None) -> Task | None:
        """
        Claim the highest-priority pending task and mark it in_progress.

        Args:
            task_type: If set, restrict to tasks of this type only

        Returns:
            Task instance, or None if the queue is empty
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            if task_type:
                cursor = await db.execute(
                    """
                    SELECT * FROM task_queue
                    WHERE status = 'pending' AND task_type = ?
                    ORDER BY priority ASC, created_at ASC
                    LIMIT 1
                    """,
                    (task_type,),
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT * FROM task_queue
                    WHERE status = 'pending'
                    ORDER BY priority ASC, created_at ASC
                    LIMIT 1
                    """
                )

            row = await cursor.fetchone()
            if not row:
                return None

            # Claim atomically before releasing the connection
            await db.execute(
                """
                UPDATE task_queue
                SET status = 'in_progress', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (row["id"],),
            )
            await db.commit()

        task = Task(
            id=row["id"],
            task_type=row["task_type"],
            payload=json.loads(row["payload"]),
            status="in_progress",
            priority=row["priority"],
            chat_id=row["chat_id"],
        )
        logger.info("task_claimed", task_id=task.id, task_type=task.task_type)
        return task

    async def update(
        self,
        task_id: int,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """
        Record the outcome of a task.

        Args:
            task_id: Task to update
            status: 'done' or 'failed'
            result: Success result payload (JSON-serialisable)
            error: Error message on failure
        """
        if status not in VALID_STATUSES:
            raise ValueError(f"Unknown status {status!r}. Valid: {VALID_STATUSES}")

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE task_queue
                SET status = ?, result = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    status,
                    json.dumps(result) if result is not None else None,
                    error,
                    task_id,
                ),
            )
            await db.commit()

        logger.info("task_updated", task_id=task_id, status=status)

    async def get(self, task_id: int) -> Task | None:
        """Fetch a single task by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM task_queue WHERE id = ?", (task_id,))
            row = await cursor.fetchone()

        if not row:
            return None

        return Task(
            id=row["id"],
            task_type=row["task_type"],
            payload=json.loads(row["payload"]),
            status=row["status"],
            priority=row["priority"],
            chat_id=row["chat_id"],
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
        )

    async def depth(self, status: str = "pending") -> int:
        """Return the number of tasks with the given status."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM task_queue WHERE status = ?", (status,))
            row = await cursor.fetchone()
        return row[0] if row else 0
