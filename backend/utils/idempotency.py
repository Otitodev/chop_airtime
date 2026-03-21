"""Deterministic idempotency key generation for VTU disbursements."""

import hashlib


def generate_idempotency_key(session_id: str, phone_number: str, amount: float) -> str:
    """
    Generate a SHA-256-based idempotency key.

    The key is deterministic: same session + phone + amount always produce
    the same key, acting as a database-level double-spend guard.
    """
    raw = f"{session_id}:{phone_number}:{amount:.2f}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
