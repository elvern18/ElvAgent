"""
MemoryStore — short-term per-chat conversation context with TTL expiry.

Pure in-memory dict keyed by chat_id. No locks needed (single asyncio event loop).
Each message has a timestamp; expired messages are pruned on access.
"""

import time
from dataclasses import dataclass, field


@dataclass
class Message:
    role: str  # "user" or "assistant"
    content: str
    ts: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content, "ts": self.ts}


class MemoryStore:
    """
    Short-term per-chat conversation context with TTL expiry.

    Used by TelegramAgent to store recent conversation turns per chat_id,
    and by TaskWorker to record assistant replies back into the same context.
    """

    def __init__(self, ttl_seconds: int = 3600, max_messages: int = 20) -> None:
        self._ttl = ttl_seconds
        self._max = max_messages
        self._store: dict[int, list[Message]] = {}

    def add_message(self, chat_id: int, role: str, content: str) -> None:
        """Append a message for chat_id, then prune expired and trim to max."""
        msgs = self._store.setdefault(chat_id, [])
        msgs.append(Message(role=role, content=content))
        now = time.time()
        active = [m for m in msgs if now - m.ts < self._ttl]
        if len(active) > self._max:
            active = active[-self._max :]
        self._store[chat_id] = active

    def get_context(self, chat_id: int) -> list[Message]:
        """Return a copy of non-expired messages for chat_id."""
        return list(self._active(chat_id, time.time()))

    def format_for_prompt(self, chat_id: int) -> str:
        """
        Format recent conversation as a text block for inclusion in prompts.

        Returns empty string if no messages exist.
        """
        msgs = self._active(chat_id, time.time())
        if not msgs:
            return ""
        lines = [f"[{m.role}] {m.content}" for m in msgs]
        return "Recent conversation:\n" + "\n".join(lines)

    def clear(self, chat_id: int) -> None:
        """Remove all messages for the given chat_id."""
        self._store.pop(chat_id, None)

    def _active(self, chat_id: int, now: float) -> list[Message]:
        """Return non-expired messages for chat_id (does not mutate store)."""
        msgs = self._store.get(chat_id, [])
        return [m for m in msgs if now - m.ts < self._ttl]
