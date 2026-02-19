"""
SQLite-backed priority task queue for the PA system.

Tasks are pushed by incoming sources (e.g. Telegram commands) and processed
by the TaskWorker agent. Priority 1 = highest, 10 = lowest.

Clarification flow
------------------
When CodeHandler decides it needs to ask the user clarifying questions before
coding, it returns status="waiting_clarification".  TaskWorker calls
await_clarification() to persist the paused state with a 10-minute deadline.

When the user replies, TelegramAgent calls resume_with_answer() to inject the
answer into the task payload and reset the status to "pending" so TaskWorker
picks it up on the next poll.

Tasks whose deadline has passed are expired by expire_stale_clarifications(),
which is called at the top of every TaskWorker poll cycle.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import aiosqlite

from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("task_queue")

VALID_TASK_TYPES = frozenset({"code", "newsletter", "status", "shell"})
VALID_STATUSES = frozenset({"pending", "in_progress", "waiting_clarification", "done", "failed"})

# How long to wait for a user clarification reply before giving up.
CLARIFICATION_TIMEOUT_MINUTES = 10


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

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

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
            status: One of VALID_STATUSES
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

    # ------------------------------------------------------------------
    # Clarification helpers
    # ------------------------------------------------------------------

    async def await_clarification(self, task_id: int) -> None:
        """Pause a task, waiting for the user to answer clarifying questions.

        Stores a deadline in the task payload so that
        expire_stale_clarifications() can time out the task if the user
        does not respond within CLARIFICATION_TIMEOUT_MINUTES.
        """
        deadline = (
            datetime.utcnow() + timedelta(minutes=CLARIFICATION_TIMEOUT_MINUTES)
        ).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT payload FROM task_queue WHERE id = ?", (task_id,))
            row = await cursor.fetchone()
            if row:
                payload = json.loads(row[0])
                payload["_clarify_deadline"] = deadline
                await db.execute(
                    """
                    UPDATE task_queue
                    SET status = 'waiting_clarification',
                        payload = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (json.dumps(payload), task_id),
                )
                await db.commit()

        logger.info("task_awaiting_clarification", task_id=task_id, deadline=deadline)

    async def find_waiting_clarification(self, chat_id: int) -> Task | None:
        """Return the most-recent waiting_clarification task for *chat_id*, or None."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM task_queue
                WHERE status = 'waiting_clarification' AND chat_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (chat_id,),
            )
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
        )

    async def resume_with_answer(self, task_id: int, answer: str) -> None:
        """Store the user's clarification answer and re-queue the task as pending.

        CodeHandler reads ``payload["clarify_answer"]`` and skips the
        clarification phase when it finds a value there.
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT payload FROM task_queue WHERE id = ?", (task_id,))
            row = await cursor.fetchone()
            if row:
                payload = json.loads(row[0])
                payload["clarify_answer"] = answer
                payload.pop("_clarify_deadline", None)
                await db.execute(
                    """
                    UPDATE task_queue
                    SET status = 'pending',
                        payload = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (json.dumps(payload), task_id),
                )
                await db.commit()

        logger.info("task_clarification_resumed", task_id=task_id)

    async def expire_stale_clarifications(self) -> list[tuple[int, int | None]]:
        """Mark timed-out waiting_clarification tasks as failed.

        Called at the top of every TaskWorker poll cycle.

        Returns:
            List of (task_id, chat_id) for each expired task so the caller
            can send the user a "timed out" message.
        """
        now_iso = datetime.utcnow().isoformat()
        expired: list[tuple[int, int | None]] = []

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, chat_id, payload FROM task_queue WHERE status = 'waiting_clarification'"
            )
            rows = await cursor.fetchall()

            for row in rows:
                payload = json.loads(row["payload"])
                deadline = payload.get("_clarify_deadline")
                if deadline and deadline < now_iso:
                    await db.execute(
                        """
                        UPDATE task_queue
                        SET status = 'failed',
                            error = 'Timed out waiting for clarification',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (row["id"],),
                    )
                    expired.append((row["id"], row["chat_id"]))

            if expired:
                await db.commit()

        for task_id, _ in expired:
            logger.info("task_clarification_expired", task_id=task_id)

        return expired
