import threading
import time

_store = {}
_lock = threading.Lock()


def get(key):
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() >= expires_at:
            del _store[key]
            return None
        return value


def set(key, value, ttl_seconds):
    with _lock:
        _store[key] = (value, time.time() + ttl_seconds)


def clear():
    with _lock:
        _store.clear()
