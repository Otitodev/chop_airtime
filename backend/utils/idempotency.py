"""Idempotency key generation for VTU disbursements."""

import hashlib
import uuid


def generate_idempotency_key(session_id: str, phone_number: str, amount: float) -> str:
    """Deterministic key — same inputs always produce the same key.

    Kept for reference/testing. Not used for new transactions; use
    generate_new_key() instead so repeat requests get distinct keys.
    """
    raw = f"{session_id}:{phone_number}:{amount:.2f}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_new_key(session_id: str, phone_number: str, amount: float) -> str:
    """Generate a unique idempotency key for a brand-new transaction.

    Includes a UUID so the same (session, phone, amount) triple can be
    submitted multiple times as distinct, independent transactions.
    Retry of a failed transaction should reuse the key stored in state,
    not call this function again.
    """
    raw = f"{session_id}:{phone_number}:{amount:.2f}:{uuid.uuid4()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
