"""Evolution API helper — send WhatsApp messages."""

from __future__ import annotations

import logging

import httpx

from config import get_settings

logger = logging.getLogger(__name__)


async def send_message(to: str, text: str) -> bool:
    """
    Send a text message via Evolution API.

    Args:
        to: Recipient's WhatsApp number in international format (e.g. '2348031234567').
        text: Message body.

    Returns:
        True on success, False on failure.
    """
    settings = get_settings()
    if not settings.evolution_api_url or not settings.evolution_api_instance:
        logger.warning("Evolution API not configured — skipping message send")
        return False

    url = (
        f"{settings.evolution_api_url.rstrip('/')}"
        f"/message/sendText/{settings.evolution_api_instance}"
    )
    headers = {
        "apikey": settings.evolution_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "number": to,
        "text": text,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code < 300:
            logger.info("Evolution API: message sent to %s", to)
            return True
        logger.warning("Evolution API returned %d: %s", resp.status_code, resp.text)
        return False
    except Exception as exc:
        logger.error("Evolution API send failed: %s", exc)
        return False
