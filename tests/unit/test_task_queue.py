"""
Unit tests for TaskQueue.

Uses a temporary in-memory SQLite database (not the production state.db).
"""

from datetime import datetime, timedelta

import pytest
import pytest_asyncio

from src.core.state_manager import StateManager
from src.core.task_queue import VALID_STATUSES, VALID_TASK_TYPES, TaskQueue


@pytest_asyncio.fixture
async def db_path(tmp_path):
    """Provide a temporary database with the schema initialised."""
    path = tmp_path / "test_state.db"
    sm = StateManager(db_path=path)
    await sm.init_db()
    return path


@pytest_asyncio.fixture
async def queue(db_path):
    """TaskQueue backed by the temporary database."""
    return TaskQueue(db_path=db_path)


# ---------------------------------------------------------------------------
# push
# ---------------------------------------------------------------------------


class TestPush:
    async def test_returns_positive_id(self, queue):
        task_id = await queue.push("status", {"msg": "hi"})
        assert task_id > 0

    async def test_increments_id_per_push(self, queue):
        id1 = await queue.push("status", {})
        id2 = await queue.push("newsletter", {})
        assert id2 > id1

    async def test_rejects_unknown_task_type(self, queue):
        with pytest.raises(ValueError, match="Unknown task_type"):
            await queue.push("unknown_type", {})

    async def test_all_valid_task_types_accepted(self, queue):
        for task_type in VALID_TASK_TYPES:
            task_id = await queue.push(task_type, {})
            assert task_id > 0

    async def test_stores_chat_id(self, queue):
        task_id = await queue.push("status", {}, chat_id=42)
        task = await queue.get(task_id)
        assert task.chat_id == 42

    async def test_default_priority_is_five(self, queue):
        task_id = await queue.push("status", {})
        task = await queue.get(task_id)
        assert task.priority == 5


# ---------------------------------------------------------------------------
# pop
# ---------------------------------------------------------------------------


class TestPop:
    async def test_returns_none_on_empty_queue(self, queue):
        assert await queue.pop() is None

    async def test_returns_highest_priority_first(self, queue):
        await queue.push("status", {"n": "low"}, priority=8)
        await queue.push("status", {"n": "high"}, priority=1)
        task = await queue.pop()
        assert task.payload["n"] == "high"

    async def test_marks_task_in_progress(self, queue):
        task_id = await queue.push("status", {})
        task = await queue.pop()
        assert task.id == task_id
        assert task.status == "in_progress"

        # Verify status persisted to DB
        fetched = await queue.get(task_id)
        assert fetched.status == "in_progress"

    async def test_does_not_return_in_progress_tasks(self, queue):
        await queue.push("status", {})
        await queue.pop()  # claims it
        assert await queue.pop() is None

    async def test_filter_by_task_type(self, queue):
        await queue.push("newsletter", {})
        code_id = await queue.push("code", {"instruction": "x"})
        task = await queue.pop(task_type="code")
        assert task.id == code_id

    async def test_filter_returns_none_if_no_matching_type(self, queue):
        await queue.push("newsletter", {})
        assert await queue.pop(task_type="code") is None

    async def test_fifo_within_same_priority(self, queue):
        id1 = await queue.push("status", {"n": 1}, priority=5)
        id2 = await queue.push("status", {"n": 2}, priority=5)
        first = await queue.pop()
        assert first.id == id1
        second = await queue.pop()
        assert second.id == id2


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


class TestUpdate:
    async def test_marks_done_with_result(self, queue):
        task_id = await queue.push("status", {})
        await queue.pop()
        await queue.update(task_id, status="done", result={"msg": "ok"})
        task = await queue.get(task_id)
        assert task.status == "done"
        assert task.result == {"msg": "ok"}

    async def test_marks_failed_with_error(self, queue):
        task_id = await queue.push("status", {})
        await queue.pop()
        await queue.update(task_id, status="failed", error="boom")
        task = await queue.get(task_id)
        assert task.status == "failed"
        assert task.error == "boom"

    async def test_rejects_unknown_status(self, queue):
        task_id = await queue.push("status", {})
        with pytest.raises(ValueError, match="Unknown status"):
            await queue.update(task_id, status="wibble")


# ---------------------------------------------------------------------------
# depth
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# waiting_clarification status
# ---------------------------------------------------------------------------


class TestValidStatuses:
    def test_waiting_clarification_is_valid(self):
        assert "waiting_clarification" in VALID_STATUSES

    async def test_update_accepts_waiting_clarification(self, queue):
        task_id = await queue.push("code", {"instruction": "x"})
        await queue.pop()
        # Should not raise
        await queue.update(task_id, status="waiting_clarification")
        task = await queue.get(task_id)
        assert task.status == "waiting_clarification"


# ---------------------------------------------------------------------------
# Clarification helpers
# ---------------------------------------------------------------------------


class TestClarificationHelpers:
    async def test_await_clarification_sets_status(self, queue):
        task_id = await queue.push("code", {"instruction": "x"}, chat_id=99)
        await queue.pop()
        await queue.await_clarification(task_id)
        task = await queue.get(task_id)
        assert task.status == "waiting_clarification"

    async def test_await_clarification_stores_deadline(self, queue):
        task_id = await queue.push("code", {"instruction": "x"}, chat_id=99)
        await queue.pop()
        await queue.await_clarification(task_id)
        task = await queue.get(task_id)
        assert "_clarify_deadline" in task.payload

    async def test_find_waiting_clarification_returns_task(self, queue):
        task_id = await queue.push("code", {"instruction": "x"}, chat_id=55)
        await queue.pop()
        await queue.await_clarification(task_id)
        found = await queue.find_waiting_clarification(chat_id=55)
        assert found is not None
        assert found.id == task_id

    async def test_find_waiting_clarification_returns_none_for_other_chat(self, queue):
        task_id = await queue.push("code", {"instruction": "x"}, chat_id=55)
        await queue.pop()
        await queue.await_clarification(task_id)
        found = await queue.find_waiting_clarification(chat_id=999)
        assert found is None

    async def test_find_waiting_clarification_returns_none_when_none_waiting(self, queue):
        found = await queue.find_waiting_clarification(chat_id=55)
        assert found is None

    async def test_resume_with_answer_sets_pending_and_stores_answer(self, queue):
        task_id = await queue.push("code", {"instruction": "x"}, chat_id=55)
        await queue.pop()
        await queue.await_clarification(task_id)
        await queue.resume_with_answer(task_id, "my answer")
        task = await queue.get(task_id)
        assert task.status == "pending"
        assert task.payload["clarify_answer"] == "my answer"

    async def test_resume_with_answer_removes_deadline(self, queue):
        task_id = await queue.push("code", {"instruction": "x"}, chat_id=55)
        await queue.pop()
        await queue.await_clarification(task_id)
        await queue.resume_with_answer(task_id, "answer")
        task = await queue.get(task_id)
        assert "_clarify_deadline" not in task.payload

    async def test_expire_stale_clarifications_marks_failed(self, queue):
        task_id = await queue.push("code", {"instruction": "x"}, chat_id=55)
        await queue.pop()
        await queue.await_clarification(task_id)
        # Manually backdate the deadline to simulate expiry
        import json

        async with __import__("aiosqlite").connect(queue.db_path) as db:
            cursor = await db.execute("SELECT payload FROM task_queue WHERE id = ?", (task_id,))
            row = await cursor.fetchone()
            payload = json.loads(row[0])
            payload["_clarify_deadline"] = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
            await db.execute(
                "UPDATE task_queue SET payload = ? WHERE id = ?",
                (json.dumps(payload), task_id),
            )
            await db.commit()

        expired = await queue.expire_stale_clarifications()
        assert any(t[0] == task_id for t in expired)
        task = await queue.get(task_id)
        assert task.status == "failed"
        assert "Timed out" in (task.error or "")

    async def test_expire_stale_clarifications_returns_chat_id(self, queue):
        import json

        task_id = await queue.push("code", {"instruction": "x"}, chat_id=77)
        await queue.pop()
        await queue.await_clarification(task_id)
        async with __import__("aiosqlite").connect(queue.db_path) as db:
            cursor = await db.execute("SELECT payload FROM task_queue WHERE id = ?", (task_id,))
            row = await cursor.fetchone()
            payload = json.loads(row[0])
            payload["_clarify_deadline"] = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
            await db.execute(
                "UPDATE task_queue SET payload = ? WHERE id = ?",
                (json.dumps(payload), task_id),
            )
            await db.commit()

        expired = await queue.expire_stale_clarifications()
        chat_ids = [chat_id for _, chat_id in expired]
        assert 77 in chat_ids

    async def test_expire_stale_does_not_expire_fresh_task(self, queue):
        task_id = await queue.push("code", {"instruction": "x"}, chat_id=55)
        await queue.pop()
        await queue.await_clarification(task_id)
        expired = await queue.expire_stale_clarifications()
        # Deadline is 10 minutes in the future — should not expire
        assert not any(t[0] == task_id for t in expired)


class TestDepth:
    async def test_zero_on_empty(self, queue):
        assert await queue.depth() == 0

    async def test_counts_pending(self, queue):
        await queue.push("status", {})
        await queue.push("status", {})
        assert await queue.depth("pending") == 2

    async def test_counts_in_progress(self, queue):
        await queue.push("status", {})
        await queue.pop()
        assert await queue.depth("in_progress") == 1
        assert await queue.depth("pending") == 0

    async def test_counts_done(self, queue):
        task_id = await queue.push("status", {})
        await queue.pop()
        await queue.update(task_id, status="done")
        assert await queue.depth("done") == 1
        assert await queue.depth("pending") == 0
