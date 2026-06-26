"""Per-session sliding-window rate limiter."""

from __future__ import annotations

import time
from collections import deque
from threading import Lock

from app.exceptions import RateLimitError


class RateLimiter:
    """Thread-safe sliding-window rate limiter keyed by session ID.

    Args:
        max_requests: Maximum number of requests allowed per *window_seconds*.
        window_seconds: Length of the sliding window in seconds.
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._windows: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, session_id: str) -> None:
        """Record a request for *session_id* and raise if the rate is exceeded."""
        now = time.monotonic()
        cutoff = now - self._window_seconds

        with self._lock:
            if session_id not in self._windows:
                self._windows[session_id] = deque()

            window = self._windows[session_id]

            # Evict timestamps outside the current window
            while window and window[0] < cutoff:
                window.popleft()

            if len(window) >= self._max_requests:
                raise RateLimitError(
                    f"You're sending messages too quickly. "
                    f"Please wait a moment before trying again."
                )

            window.append(now)

    def clear(self, session_id: str) -> None:
        """Remove the rate-limit window for *session_id* (called on session clear)."""
        with self._lock:
            self._windows.pop(session_id, None)
