"""POST /webhook/whatsapp — Evolution API webhook with HMAC validation."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from agent.graph import get_graph
from agent.state import AgentState
from config import get_settings
from services.evolution import send_message

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory session store for WhatsApp: phone_number → messages
_wa_sessions: Dict[str, List[BaseMessage]] = {}


def _validate_hmac(body_bytes: bytes, signature_header: str | None, secret: str) -> None:
    """Raise HTTP 403 if HMAC signature is invalid."""
    if not secret:
        # No secret configured — skip validation (dev mode)
        return
    if not signature_header:
        raise HTTPException(status_code=403, detail="Missing HMAC signature")

    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature_header, expected):
        raise HTTPException(status_code=403, detail="Invalid HMAC signature")


def _extract_message(payload: dict) -> tuple[str, str] | None:
    """
    Extract (from_number, message_text) from Evolution API webhook payload.
    Returns None if the event is not a text message.
    """
    try:
        data = payload.get("data", {})
        msg = data.get("message", {})
        text = msg.get("conversation") or msg.get("extendedTextMessage", {}).get("text")
        from_number = data.get("key", {}).get("remoteJid", "").replace("@s.whatsapp.net", "")
        if text and from_number:
            return from_number, text
    except Exception as exc:
        logger.warning("Could not parse webhook payload: %s", exc)
    return None


def _get_last_ai_text(messages: list) -> str | None:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = msg.content
            if isinstance(content, str) and not content.startswith("_"):
                return content
    return None


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    body_bytes = await request.body()
    settings = get_settings()

    # HMAC validation
    sig_header = request.headers.get("x-hub-signature-256")
    _validate_hmac(body_bytes, sig_header, settings.evolution_api_webhook_secret)

    payload: dict = json.loads(body_bytes)
    logger.debug("WhatsApp webhook payload: %s", payload)

    # Only process message events
    event = payload.get("event", "")
    if event != "messages.upsert":
        return {"status": "ignored", "event": event}

    extracted = _extract_message(payload)
    if not extracted:
        return {"status": "ignored", "reason": "not a text message"}

    from_number, text = extracted
    graph = get_graph()
    existing_messages = _wa_sessions.get(from_number, [])

    if not existing_messages:
        # First message — run full flow starting from greet
        initial_state: AgentState = {
            "messages": [HumanMessage(content=text)],
            "session_id": from_number,
            "channel": "whatsapp",
            "identifier": from_number,
            "phone_number": None,
            "network": None,
            "amount": None,
            "user_id": None,
            "user_total": None,
            "confirmed": None,
            "tx_id": None,
            "idempotency_key": None,
            "vtu_status": None,
            "error_message": None,
            "next": None,
        }
    else:
        initial_state = {
            "messages": existing_messages + [HumanMessage(content=text)],
            "session_id": from_number,
            "channel": "whatsapp",
            "identifier": from_number,
            "phone_number": None,
            "network": None,
            "amount": None,
            "user_id": None,
            "user_total": None,
            "confirmed": None,
            "tx_id": None,
            "idempotency_key": None,
            "vtu_status": None,
            "error_message": None,
            "next": "collect_slots",
        }

    result = await graph.ainvoke(initial_state)
    _wa_sessions[from_number] = list(result["messages"])

    reply = _get_last_ai_text(result["messages"])
    if reply:
        await send_message(from_number, reply)

    return {"status": "ok"}
