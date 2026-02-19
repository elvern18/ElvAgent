"""
Unit tests for MemoryStore.

All tests are synchronous (MemoryStore has no async methods).
Uses unittest.mock.patch to freeze time.time() where TTL behaviour is tested.
"""

from unittest.mock import patch

from src.memory.memory_store import MemoryStore, Message

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store(ttl: int = 3600, max_messages: int = 20) -> MemoryStore:
    return MemoryStore(ttl_seconds=ttl, max_messages=max_messages)


# ---------------------------------------------------------------------------
# TestAddMessage
# ---------------------------------------------------------------------------


class TestAddMessage:
    def test_adds_message_to_empty_chat(self):
        store = _store()
        store.add_message(1, "user", "hello")
        assert len(store.get_context(1)) == 1

    def test_message_has_correct_role_and_content(self):
        store = _store()
        store.add_message(1, "assistant", "world")
        msg = store.get_context(1)[0]
        assert msg.role == "assistant"
        assert msg.content == "world"

    def test_multiple_messages_stored_in_order(self):
        store = _store()
        store.add_message(1, "user", "first")
        store.add_message(1, "assistant", "second")
        msgs = store.get_context(1)
        assert msgs[0].content == "first"
        assert msgs[1].content == "second"

    def test_enforces_max_messages_cap(self):
        store = _store(max_messages=3)
        for i in range(5):
            store.add_message(1, "user", f"msg {i}")
        msgs = store.get_context(1)
        assert len(msgs) == 3
        # Oldest are dropped; newest are kept
        assert msgs[-1].content == "msg 4"

    def test_prunes_expired_on_add(self):
        store = _store(ttl=100)
        # Add a message that is already expired (ts far in the past)
        with patch("time.time", return_value=0.0):
            store.add_message(1, "user", "old")
        # Now add a fresh message at t=200 (> ttl of 100)
        with patch("time.time", return_value=200.0):
            store.add_message(1, "user", "new")
            msgs = store.get_context(1)
        assert len(msgs) == 1
        assert msgs[0].content == "new"

    def test_different_chats_are_independent(self):
        store = _store()
        store.add_message(1, "user", "chat1")
        store.add_message(2, "user", "chat2")
        assert len(store.get_context(1)) == 1
        assert len(store.get_context(2)) == 1


# ---------------------------------------------------------------------------
# TestGetContext
# ---------------------------------------------------------------------------


class TestGetContext:
    def test_empty_chat_returns_empty_list(self):
        store = _store()
        assert store.get_context(999) == []

    def test_returns_non_expired_messages(self):
        store = _store(ttl=100)
        with patch("time.time", return_value=0.0):
            store.add_message(1, "user", "fresh")
        with patch("time.time", return_value=50.0):
            msgs = store.get_context(1)
        assert len(msgs) == 1

    def test_excludes_expired_messages(self):
        store = _store(ttl=100)
        with patch("time.time", return_value=0.0):
            store.add_message(1, "user", "expired")
        with patch("time.time", return_value=200.0):
            msgs = store.get_context(1)
        assert msgs == []

    def test_ttl_boundary_exclusive(self):
        """Message at exactly TTL seconds old should be expired."""
        store = _store(ttl=100)
        with patch("time.time", return_value=0.0):
            store.add_message(1, "user", "boundary")
        # Exactly at TTL: now - ts == 100, condition is `< ttl` so this expires
        with patch("time.time", return_value=100.0):
            msgs = store.get_context(1)
        assert msgs == []

    def test_returns_copy_not_reference(self):
        """Mutating the returned list does not affect internal state."""
        store = _store()
        store.add_message(1, "user", "msg")
        ctx = store.get_context(1)
        ctx.clear()
        assert len(store.get_context(1)) == 1


# ---------------------------------------------------------------------------
# TestFormatForPrompt
# ---------------------------------------------------------------------------


class TestFormatForPrompt:
    def test_empty_chat_returns_empty_string(self):
        store = _store()
        assert store.format_for_prompt(999) == ""

    def test_non_empty_starts_with_header(self):
        store = _store()
        store.add_message(1, "user", "hi")
        result = store.format_for_prompt(1)
        assert result.startswith("Recent conversation:")

    def test_contains_role_and_content(self):
        store = _store()
        store.add_message(1, "user", "hello there")
        store.add_message(1, "assistant", "hi back")
        result = store.format_for_prompt(1)
        assert "[user] hello there" in result
        assert "[assistant] hi back" in result

    def test_expired_messages_excluded_from_format(self):
        store = _store(ttl=100)
        with patch("time.time", return_value=0.0):
            store.add_message(1, "user", "old message")
        with patch("time.time", return_value=200.0):
            result = store.format_for_prompt(1)
        assert result == ""

    def test_messages_appear_in_chronological_order(self):
        store = _store()
        store.add_message(1, "user", "first")
        store.add_message(1, "assistant", "second")
        result = store.format_for_prompt(1)
        assert result.index("[user] first") < result.index("[assistant] second")


# ---------------------------------------------------------------------------
# TestClear
# ---------------------------------------------------------------------------


class TestClear:
    def test_clear_removes_all_messages_for_chat(self):
        store = _store()
        store.add_message(1, "user", "a")
        store.add_message(1, "assistant", "b")
        store.clear(1)
        assert store.get_context(1) == []

    def test_clear_does_not_affect_other_chats(self):
        store = _store()
        store.add_message(1, "user", "a")
        store.add_message(2, "user", "b")
        store.clear(1)
        assert store.get_context(2) == [
            Message(role="user", content="b", ts=store.get_context(2)[0].ts)
        ]

    def test_clear_nonexistent_chat_does_not_raise(self):
        store = _store()
        store.clear(999)  # should not raise


# ---------------------------------------------------------------------------
# TestChatIsolation
# ---------------------------------------------------------------------------


class TestChatIsolation:
    def test_two_chats_stay_separate(self):
        store = _store()
        store.add_message(10, "user", "chat 10 msg")
        store.add_message(20, "user", "chat 20 msg")
        ctx10 = store.get_context(10)
        ctx20 = store.get_context(20)
        assert ctx10[0].content == "chat 10 msg"
        assert ctx20[0].content == "chat 20 msg"

    def test_clearing_one_chat_leaves_others_intact(self):
        store = _store()
        store.add_message(10, "user", "keep me")
        store.add_message(20, "user", "delete me")
        store.clear(20)
        assert len(store.get_context(10)) == 1
        assert len(store.get_context(20)) == 0

    def test_max_cap_per_chat_independent(self):
        store = _store(max_messages=2)
        store.add_message(1, "user", "a")
        store.add_message(1, "user", "b")
        store.add_message(1, "user", "c")  # pushes "a" out
        store.add_message(2, "user", "x")  # chat 2 unaffected
        assert len(store.get_context(1)) == 2
        assert len(store.get_context(2)) == 1


# ---------------------------------------------------------------------------
# TestMessageToDict
# ---------------------------------------------------------------------------


class TestMessageToDict:
    def test_to_dict_contains_all_fields(self):
        msg = Message(role="user", content="hello", ts=1234.5)
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "hello"
        assert d["ts"] == 1234.5

    def test_to_dict_roundtrip(self):
        msg = Message(role="assistant", content="reply", ts=9999.0)
        d = msg.to_dict()
        assert d == {"role": "assistant", "content": "reply", "ts": 9999.0}
