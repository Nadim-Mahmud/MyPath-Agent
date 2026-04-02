"""In-memory per-session conversation history store."""

from __future__ import annotations

from collections import deque
from threading import Lock


class SessionStore:
    """Thread-safe in-memory store for per-session conversation history.

    Each session holds a bounded deque of Gemini-format message dicts
    (``{"role": ..., "parts": [{"text": ...}]}``).
    """

    def __init__(self, max_messages: int) -> None:
        self._max_messages = max_messages
        self._store: dict[str, deque] = {}
        self._lock = Lock()

    def get_history(self, session_id: str) -> list[dict]:
        """Return the current message history for *session_id* as a plain list."""
        with self._lock:
            return list(self._store.get(session_id, deque()))

    def add_message(self, session_id: str, role: str, text: str) -> None:
        """Append a new message to the history, evicting the oldest when at capacity."""
        with self._lock:
            if session_id not in self._store:
                self._store[session_id] = deque(maxlen=self._max_messages)
            self._store[session_id].append({"role": role, "parts": [{"text": text}]})

    def clear_session(self, session_id: str) -> None:
        """Delete all history for *session_id* (no-op if unknown)."""
        with self._lock:
            self._store.pop(session_id, None)
