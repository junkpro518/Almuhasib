import time
import uuid
from threading import Lock
from typing import Optional
from bot.parser import Transaction

_lock = Lock()
_pending: dict[str, tuple[Transaction, float]] = {}  # id -> (txn, stored_at)
_TTL_SECONDS = 3600  # entries expire after 1 hour


def store_transaction(txn: Transaction) -> str:
    """Store a pending transaction and return its 8-char ID."""
    txn_id = uuid.uuid4().hex[:8]
    with _lock:
        _evict_expired()
        _pending[txn_id] = (txn, time.monotonic())
    return txn_id


def pop_transaction(txn_id: str) -> Optional[Transaction]:
    """Retrieve and remove a pending transaction by ID. Returns None if not found or expired."""
    with _lock:
        entry = _pending.pop(txn_id, None)
        return entry[0] if entry else None


def _evict_expired() -> None:
    """Remove entries older than _TTL_SECONDS. Must be called with _lock held."""
    now = time.monotonic()
    expired = [k for k, (_, ts) in _pending.items() if now - ts > _TTL_SECONDS]
    for k in expired:
        del _pending[k]
