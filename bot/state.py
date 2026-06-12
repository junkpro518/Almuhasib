import uuid
from threading import Lock
from typing import Optional
from bot.parser import Transaction

_lock = Lock()
_pending: dict[str, Transaction] = {}


def store_transaction(txn: Transaction) -> str:
    """Store a pending transaction and return its 8-char ID."""
    txn_id = uuid.uuid4().hex[:8]
    with _lock:
        _pending[txn_id] = txn
    return txn_id


def pop_transaction(txn_id: str) -> Optional[Transaction]:
    """Retrieve and remove a pending transaction by ID. Returns None if not found."""
    with _lock:
        return _pending.pop(txn_id, None)
