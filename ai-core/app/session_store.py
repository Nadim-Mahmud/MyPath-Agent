from collections import deque
from threading import Lock
from app.config import MAX_HISTORY_MESSAGES

_store: dict[str, deque] = {}
_lock = Lock()


def get_history(session_id: str) -> list[dict]:
    with _lock:
        return list(_store.get(session_id, deque()))


def add_message(session_id: str, role: str, text: str) -> None:
    with _lock:
        if session_id not in _store:
            _store[session_id] = deque(maxlen=MAX_HISTORY_MESSAGES)
        _store[session_id].append({"role": role, "parts": [{"text": text}]})


def clear_session(session_id: str) -> None:
    with _lock:
        _store.pop(session_id, None)
