"""VTU.ng fallback VTU API client."""

from __future__ import annotations

import logging

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

_NETWORK_CODE: dict[str, str] = {
    "MTN": "mtn",
    "Airtel": "airtel",
    "Glo": "glo",
    "9mobile": "9mobile",
}


class VTUNgError(Exception):
    pass


async def disburse(
    phone_number: str,
    network: str,
    amount: float,
    idempotency_key: str,
) -> dict:
    """
    Send airtime via VTU.ng.

    Returns a dict with at minimum:
        {"success": bool, "reference": str, "raw": dict}

    Raises VTUNgError on non-retryable failures.
    """
    settings = get_settings()
    network_code = _NETWORK_CODE.get(network)
    if not network_code:
        raise VTUNgError(f"Unknown network: {network}")

    headers = {
        "Authorization": f"Bearer {settings.vtu_ng_jwt_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "request_id": idempotency_key[:50],
        "service_id": network_code,
        "phone": phone_number,
        "amount": int(amount),
    }

    # Base URL should be https://vtu.ng/wp-json — endpoint is /api/v2/airtime
    base = settings.vtu_ng_base_url.rstrip("/")
    url = f"{base}/api/v2/airtime"
    logger.info("VTU.ng request: service_id=%s phone=%s amount=%s", network_code, phone_number, amount)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)

    raw = resp.json()
    logger.info("VTU.ng response: %s", raw)

    # VTU.ng returns {"code": "success", "data": {"order_id": ..., "status": "completed-api"}}
    code = raw.get("code", "")
    reference = str(raw.get("data", {}).get("order_id", idempotency_key))

    if code == "success":
        return {"success": True, "reference": reference, "raw": raw}

    # 409 duplicate_request_id means it already succeeded — treat as success
    if resp.status_code == 409 and raw.get("code") == "duplicate_request_id":
        logger.warning("VTU.ng duplicate request — treating as success")
        return {"success": True, "reference": reference, "raw": raw}

    return {"success": False, "reference": reference, "raw": raw}
