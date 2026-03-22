"""PostgreSQL database operations for Chop Airtime (Neon / any Postgres)."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Optional

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

from config import get_settings

logger = logging.getLogger(__name__)

_pool: Optional[ThreadedConnectionPool] = None


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=settings.database_url,
        )
    return _pool


@contextmanager
def _conn():
    """Yield a psycopg2 connection from the pool, auto-commit or rollback.

    Handles stale connections (closed by Supabase after idle timeout) by
    discarding the dead connection and obtaining a fresh one once.
    """
    pool = _get_pool()
    conn = pool.getconn()

    # If the connection was dropped server-side (SSL closed unexpectedly),
    # psycopg2 marks it as closed. Discard it and get a fresh one.
    if conn.closed:
        pool.putconn(conn, close=True)
        conn = pool.getconn()

    try:
        yield conn
        conn.commit()
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        # Connection is broken — discard it so the pool doesn't reuse it.
        try:
            pool.putconn(conn, close=True)
        except Exception:
            pass
        raise
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        pool.putconn(conn)
        raise
    else:
        pool.putconn(conn)


def _cursor(conn):
    """Return a DictCursor so rows behave like dicts."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------

def get_or_create_user(identifier: str, channel: str) -> dict:
    """Return existing user row or insert and return a new one."""
    with _conn() as conn:
        with _cursor(conn) as cur:
            cur.execute(
                "SELECT * FROM users WHERE identifier = %s",
                (identifier,),
            )
            row = cur.fetchone()
            if row:
                return dict(row)

            cur.execute(
                """
                INSERT INTO users (identifier, channel, total_received)
                VALUES (%s, %s, 0)
                RETURNING *
                """,
                (identifier, channel),
            )
            return dict(cur.fetchone())


def get_user_total(identifier: str) -> float:
    """Return cumulative total_received for a user, or 0 if unknown."""
    with _conn() as conn:
        with _cursor(conn) as cur:
            cur.execute(
                "SELECT total_received FROM users WHERE identifier = %s",
                (identifier,),
            )
            row = cur.fetchone()
            return float(row["total_received"]) if row else 0.0


def increment_user_total(user_id: str, amount: float) -> None:
    """Atomically increment total_received using a single UPDATE statement."""
    with _conn() as conn:
        with _cursor(conn) as cur:
            cur.execute(
                "UPDATE users SET total_received = total_received + %s WHERE id = %s",
                (amount, user_id),
            )


# ---------------------------------------------------------------------------
# Transaction operations
# ---------------------------------------------------------------------------

def create_transaction(
    user_id: str,
    phone_number: str,
    network: str,
    amount: float,
    idempotency_key: str,
) -> dict:
    """Insert a pending transaction and return the row."""
    with _conn() as conn:
        with _cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO transactions
                    (user_id, phone_number, network, amount, status, idempotency_key)
                VALUES (%s, %s, %s, %s, 'pending', %s)
                RETURNING *
                """,
                (user_id, phone_number, network, amount, idempotency_key),
            )
            return dict(cur.fetchone())


def update_transaction_status(
    tx_id: str,
    status: str,
    vtu_reference: Optional[str] = None,
    vtu_response: Optional[dict] = None,
) -> None:
    """Update transaction status and optional VTU metadata."""
    import json

    with _conn() as conn:
        with _cursor(conn) as cur:
            cur.execute(
                """
                UPDATE transactions
                SET status = %s,
                    vtu_reference = COALESCE(%s, vtu_reference),
                    vtu_response  = COALESCE(%s::jsonb, vtu_response)
                WHERE id = %s
                """,
                (
                    status,
                    vtu_reference,
                    json.dumps(vtu_response) if vtu_response is not None else None,
                    tx_id,
                ),
            )


def get_transaction_by_idempotency_key(key: str) -> Optional[dict]:
    """Return the transaction row for a given idempotency key, or None."""
    with _conn() as conn:
        with _cursor(conn) as cur:
            cur.execute(
                "SELECT * FROM transactions WHERE idempotency_key = %s",
                (key,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


# ---------------------------------------------------------------------------
# Wallet snapshot operations
# ---------------------------------------------------------------------------

def save_wallet_snapshot(balance: float) -> None:
    """Record a wallet balance snapshot."""
    with _conn() as conn:
        with _cursor(conn) as cur:
            cur.execute(
                "INSERT INTO wallet_snapshots (balance) VALUES (%s)",
                (balance,),
            )


def get_latest_wallet_snapshot() -> Optional[float]:
    """Return the most recent wallet balance or None."""
    with _conn() as conn:
        with _cursor(conn) as cur:
            cur.execute(
                "SELECT balance FROM wallet_snapshots ORDER BY snapshot_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            return float(row["balance"]) if row else None
