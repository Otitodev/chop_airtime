"""POST /chat — web chat endpoint."""

from __future__ import annotations

import logging
from typing import Dict

from fastapi import APIRouter
from langchain_core.messages import HumanMessage, AIMessage

from agent.graph import get_graph
from agent.state import AgentState
from models import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Full AgentState persisted per session (not just messages).
# This preserves slots (phone_number, network, amount, etc.) across HTTP requests.
# Swap for Redis post-MVP.
_sessions: Dict[str, dict] = {}


def _get_last_ai_message(messages: list) -> str:
    """Return the last non-internal AIMessage content."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = msg.content
            if isinstance(content, str) and not content.startswith("_"):
                return content
    return "No wahala, I dey here! How I fit help you?"


def _blank_state(session_id: str) -> AgentState:
    return {
        "messages": [],
        "session_id": session_id,
        "channel": "web",
        "identifier": session_id,
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


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.session_id
    graph = get_graph()
    prev = _sessions.get(session_id)

    # ── First ever call with no message → trigger greeting ──────────────────
    if prev is None and not request.message:
        result = await graph.ainvoke(_blank_state(session_id))
        _sessions[session_id] = dict(result)
        reply = _get_last_ai_message(result["messages"])
        return ChatResponse(session_id=session_id, reply=reply)

    # ── Returning call with a user message ───────────────────────────────────
    if prev is None:
        # Message arrived before greeting (e.g. direct API call) — start fresh
        prev = _blank_state(session_id)

    # Determine which node to resume at based on how far the conversation has progressed.
    # - All slots filled + validated (user_id set) → waiting at confirm
    # - Otherwise → still collecting slots
    slots_complete = (
        prev.get("phone_number")
        and prev.get("network")
        and prev.get("amount")
        and prev.get("user_id")
    )
    resume_at = "confirm" if slots_complete else "collect_slots"

    new_message = HumanMessage(content=request.message)
    current_state: AgentState = {
        **prev,  # restore all slots and DB references
        "messages": list(prev.get("messages", [])) + [new_message],
        "next": resume_at,
    }

    result = await graph.ainvoke(current_state)
    _sessions[session_id] = dict(result)
    reply = _get_last_ai_message(result["messages"])
    return ChatResponse(session_id=session_id, reply=reply)
