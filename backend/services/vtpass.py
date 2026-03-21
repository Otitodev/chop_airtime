"""VTpass VTU API client."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from config import get_settings
from utils.network_detect import get_vtpass_service_id

logger = logging.getLogger(__name__)


class VTpassError(Exception):
    pass


async def disburse(
    phone_number: str,
    network: str,
    amount: float,
    idempotency_key: str,
) -> dict:
    """
    Send airtime via VTpass.

    Returns a dict with at minimum:
        {"success": bool, "reference": str, "raw": dict}

    Raises VTpassError on non-retryable failures.
    """
    settings = get_settings()
    service_id = get_vtpass_service_id(network)
    if not service_id:
        raise VTpassError(f"Unknown network: {network}")

    payload = {
        "request_id": idempotency_key[:50],  # VTpass limit
        "serviceID": service_id,
        "amount": int(amount),
        "phone": phone_number,
    }

    headers = {
        "api-key": settings.vtpass_api_key,
        "secret-key": settings.vtpass_secret_key,
        "Content-Type": "application/json",
    }

    url = f"{settings.vtpass_base_url}/pay"
    logger.info("VTpass request: service=%s phone=%s amount=%s", service_id, phone_number, amount)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)

    raw = resp.json()
    logger.info("VTpass response: %s", raw)

    # VTpass uses code "000" for success
    code = str(raw.get("code", ""))
    reference = raw.get("content", {}).get("transactions", {}).get("transactionId", "")

    if code == "000":
        return {"success": True, "reference": reference, "raw": raw}

    # Non-success but parseable
    return {"success": False, "reference": reference, "raw": raw}
