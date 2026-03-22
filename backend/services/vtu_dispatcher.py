"""VTU dispatcher: VTU.ng primary → VTpass fallback."""

from __future__ import annotations

import logging

from services import vtpass, vtu_ng

logger = logging.getLogger(__name__)


async def disburse(
    phone_number: str,
    network: str,
    amount: float,
    idempotency_key: str,
) -> dict:
    """
    Attempt VTU.ng first. On failure, retry once, then fall back to VTpass.

    Returns:
        {"success": bool, "reference": str, "provider": str, "raw": dict}
    """
    # VTU.ng codes that mean "definitively failed — do not retry same key"
    _TERMINAL_CODES = {"duplicate_request_id", "duplicate_order"}

    # --- Primary: VTU.ng ---
    for attempt in range(2):
        try:
            result = await vtu_ng.disburse(phone_number, network, amount, idempotency_key)
            if result["success"]:
                logger.info("VTU.ng succeeded on attempt %d", attempt + 1)
                return {**result, "provider": "vtu_ng"}
            code = str(result["raw"].get("code", ""))
            logger.warning("VTU.ng non-success attempt %d (code %s)", attempt + 1, code)
            if code in _TERMINAL_CODES:
                break
        except Exception as exc:
            logger.warning("VTU.ng attempt %d raised: %s", attempt + 1, exc)

    # --- Fallback: VTpass ---
    logger.info("Falling back to VTpass")
    try:
        result = await vtpass.disburse(phone_number, network, amount, idempotency_key)
        return {**result, "provider": "vtpass"}
    except Exception as exc:
        logger.error("VTpass also failed: %s", exc)
        return {"success": False, "reference": "", "provider": "vtpass", "raw": {"error": str(exc)}}
