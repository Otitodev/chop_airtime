"""VTU dispatcher: VTpass primary → VTU.ng fallback."""

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
    Attempt VTpass first. On failure, retry once, then fall back to VTU.ng.

    Returns:
        {"success": bool, "reference": str, "provider": str, "raw": dict}
    """
    # VTpass codes that mean "definitively failed — do not retry same key"
    # 016 = transaction failed at network, 014 = request_id already exists
    _TERMINAL_CODES = {"016", "014"}

    # --- Primary: VTpass ---
    for attempt in range(2):
        try:
            result = await vtpass.disburse(phone_number, network, amount, idempotency_key)
            if result["success"]:
                logger.info("VTpass succeeded on attempt %d", attempt + 1)
                return {**result, "provider": "vtpass"}
            code = str(result["raw"].get("code", ""))
            logger.warning("VTpass non-success attempt %d (code %s)", attempt + 1, code)
            if code in _TERMINAL_CODES:
                # No point retrying — go straight to fallback
                break
        except Exception as exc:
            logger.warning("VTpass attempt %d raised: %s", attempt + 1, exc)

    # --- Fallback: VTU.ng ---
    logger.info("Falling back to VTU.ng")
    try:
        result = await vtu_ng.disburse(phone_number, network, amount, idempotency_key)
        return {**result, "provider": "vtu_ng"}
    except Exception as exc:
        logger.error("VTU.ng also failed: %s", exc)
        return {"success": False, "reference": "", "provider": "vtu_ng", "raw": {"error": str(exc)}}
