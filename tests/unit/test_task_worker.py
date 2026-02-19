"""
Unit tests for TaskWorker.

Mocks StateManager, TaskQueue, and handlers so no real DB or API calls are made.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.handlers.newsletter_handler import HandlerResult
from src.agents.task_worker import TaskWorker
from src.core.task_queue import Task


def _make_task(task_type: str, payload: dict | None = None, chat_id: int | None = None) -> Task:
    return Task(id=1, task_type=task_type, payload=payload or {}, chat_id=chat_id)


def _make_worker() -> TaskWorker:
    sm = MagicMock()
    worker = TaskWorker(state_manager=sm)
    worker.task_queue = MagicMock()
    # expire_stale_clarifications is awaited in poll() — must be AsyncMock
    worker.task_queue.expire_stale_clarifications = AsyncMock(return_value=[])
    return worker


# ---------------------------------------------------------------------------
# poll
# ---------------------------------------------------------------------------


class TestPoll:
    async def test_returns_task_when_queue_has_item(self):
        worker = _make_worker()
        task = _make_task("status")
        worker.task_queue.pop = AsyncMock(return_value=task)

        result = await worker.poll()
        assert result == [task]

    async def test_returns_empty_when_queue_empty(self):
        worker = _make_worker()
        worker.task_queue.pop = AsyncMock(return_value=None)

        result = await worker.poll()
        assert result == []


# ---------------------------------------------------------------------------
# triage
# ---------------------------------------------------------------------------


class TestTriage:
    async def test_pass_through(self):
        worker = _make_worker()
        tasks = [_make_task("status"), _make_task("newsletter")]
        assert await worker.triage(tasks) == tasks

    async def test_empty_list(self):
        worker = _make_worker()
        assert await worker.triage([]) == []


# ---------------------------------------------------------------------------
# act / dispatch
# ---------------------------------------------------------------------------


class TestDispatch:
    async def test_newsletter_task_calls_newsletter_handler(self):
        worker = _make_worker()
        task = _make_task("newsletter")
        expected = HandlerResult(task=task, status="done", reply="Newsletter published!")

        with patch("src.agents.task_worker.NewsletterHandler") as MockHandler:
            MockHandler.return_value.handle = AsyncMock(return_value=expected)
            results = await worker.act([task])

        assert results == [expected]
        MockHandler.return_value.handle.assert_awaited_once_with(task)

    async def test_status_task_calls_status_handler(self):
        worker = _make_worker()
        task = _make_task("status")

        with patch("src.agents.task_worker.StatusHandler") as MockHandler:
            MockHandler.return_value.get_status = AsyncMock(return_value="ElvAgent running")
            results = await worker.act([task])

        assert results[0].status == "done"
        assert "ElvAgent running" in results[0].reply

    async def test_code_task_calls_code_handler(self):
        worker = _make_worker()
        task = _make_task("code", {"instruction": "fix the bug"})
        expected = HandlerResult(task=task, status="done", reply="PR opened!")

        with patch("src.agents.task_worker.CodeHandler") as MockHandler:
            MockHandler.return_value.handle = AsyncMock(return_value=expected)
            results = await worker.act([task])

        assert results == [expected]
        MockHandler.return_value.handle.assert_awaited_once_with(task)

    async def test_shell_task_returns_done(self):
        worker = _make_worker()
        task = _make_task("shell")
        results = await worker.act([task])
        assert results[0].status == "done"

    async def test_unknown_task_type_returns_failed(self):
        worker = _make_worker()
        task = _make_task("wibble")
        results = await worker.act([task])
        assert results[0].status == "failed"
        assert "wibble" in results[0].reply

    async def test_handler_exception_becomes_failed_result(self):
        worker = _make_worker()
        task = _make_task("newsletter")

        with patch("src.agents.task_worker.NewsletterHandler") as MockHandler:
            MockHandler.return_value.handle = AsyncMock(side_effect=RuntimeError("boom"))
            results = await worker.act([task])

        assert results[0].status == "failed"
        assert "boom" in results[0].reply
        assert results[0].error == "boom"


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


class TestRecord:
    async def test_updates_queue_on_done(self):
        worker = _make_worker()
        task = _make_task("status", chat_id=None)
        worker.task_queue.update = AsyncMock()
        result = HandlerResult(task=task, status="done", reply="ok", data={"x": 1})

        with patch.object(worker, "_send_reply", new=AsyncMock()) as mock_send:
            await worker.record([result])

        worker.task_queue.update.assert_awaited_once_with(
            task_id=1, status="done", result={"x": 1}, error=None
        )
        mock_send.assert_not_called()  # no chat_id

    async def test_sends_reply_when_chat_id_set(self):
        worker = _make_worker()
        task = _make_task("status", chat_id=99)
        worker.task_queue.update = AsyncMock()
        result = HandlerResult(task=task, status="done", reply="hello")

        with patch.object(worker, "_send_reply", new=AsyncMock()) as mock_send:
            await worker.record([result])

        mock_send.assert_awaited_once_with(99, "hello")

    async def test_updates_queue_on_failed(self):
        worker = _make_worker()
        task = _make_task("newsletter", chat_id=None)
        worker.task_queue.update = AsyncMock()
        result = HandlerResult(task=task, status="failed", reply="err", error="boom")

        with patch.object(worker, "_send_reply", new=AsyncMock()):
            await worker.record([result])

        worker.task_queue.update.assert_awaited_once_with(
            task_id=1, status="failed", result=None, error="boom"
        )

    async def test_waiting_clarification_calls_await_clarification(self):
        """waiting_clarification result pauses the task, does not call update()."""
        worker = _make_worker()
        task = _make_task("code", chat_id=55)
        worker.task_queue.update = AsyncMock()
        worker.task_queue.await_clarification = AsyncMock()
        result = HandlerResult(
            task=task,
            status="waiting_clarification",
            reply="What token symbol do you want?",
        )

        with patch.object(worker, "_send_reply", new=AsyncMock()) as mock_send:
            await worker.record([result])

        worker.task_queue.await_clarification.assert_awaited_once_with(task.id)
        worker.task_queue.update.assert_not_called()
        mock_send.assert_awaited_once_with(55, "What token symbol do you want?")

    async def test_waiting_clarification_does_not_add_to_memory(self):
        """Questions sent to the user are not stored as assistant messages."""
        worker = _make_worker()
        from src.memory.memory_store import MemoryStore

        memory = MemoryStore()
        worker.memory_store = memory
        task = _make_task("code", chat_id=55)
        worker.task_queue.await_clarification = AsyncMock()
        result = HandlerResult(
            task=task,
            status="waiting_clarification",
            reply="Some questions",
        )

        with patch.object(worker, "_send_reply", new=AsyncMock()):
            await worker.record([result])

        assert memory.get_context(55) == []

    async def test_poll_expires_stale_clarifications(self):
        """poll() calls expire_stale_clarifications before popping a task."""
        worker = _make_worker()
        worker.task_queue.expire_stale_clarifications = AsyncMock(return_value=[])
        worker.task_queue.pop = AsyncMock(return_value=None)

        await worker.poll()

        worker.task_queue.expire_stale_clarifications.assert_awaited_once()

    async def test_poll_sends_timeout_message_for_expired_task(self):
        """Expired clarification tasks trigger a Telegram notification."""
        worker = _make_worker()
        worker.task_queue.expire_stale_clarifications = AsyncMock(return_value=[(42, 99)])
        worker.task_queue.pop = AsyncMock(return_value=None)

        with patch.object(worker, "_send_reply", new=AsyncMock()) as mock_send:
            await worker.poll()

        mock_send.assert_awaited_once()
        args = mock_send.call_args[0]
        assert args[0] == 99  # correct chat_id
        assert "timed out" in args[1].lower()
