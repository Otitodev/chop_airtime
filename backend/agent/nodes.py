"""LangGraph node functions for the Chop Airtime agent."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agent.state import AgentState
from agent.prompts import (
    SYSTEM_PROMPT,
    COLLECT_SLOTS_PROMPT,
    CONFIRM_PROMPT,
    GREETING_MESSAGE,
    SUCCESS_TEMPLATE,
    FAILURE_TEMPLATE,
    CAP_EXCEEDED_TEMPLATE,
    VALIDATION_ERROR_TEMPLATE,
)
from agent.tools import extract_slots, confirm_or_reject
from utils.network_detect import detect_network, is_valid_nigerian_number
from config import get_settings
import database as db
from services import vtu_dispatcher
from services.notifier import send_low_balance_alert
from utils.idempotency import generate_idempotency_key

logger = logging.getLogger(__name__)

_TOOLS = [extract_slots, confirm_or_reject]
_TOOL_MAP = {t.name: t for t in _TOOLS}


def _make_openai(settings):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model="gpt-4o-mini", api_key=settings.openai_api_key, temperature=0.3)


def _make_mistral(settings):
    from langchain_mistralai import ChatMistralAI
    return ChatMistralAI(
        model=settings.mistral_model,
        api_key=settings.mistral_api_key,
        temperature=0.3,
    )


def _make_anthropic(settings):
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        api_key=settings.anthropic_api_key,
        temperature=0.3,
    )


_llm_cache = None


def _get_llm():
    """
    Return an LLM instance according to LLM_PROVIDER, with automatic fallback.

    Priority order based on LLM_PROVIDER setting:
      "openai"    → GPT-4o-mini → Mistral → Claude Sonnet 4.6
      "mistral"   → Mistral → GPT-4o-mini → Claude Sonnet 4.6
      "anthropic" → Claude Sonnet 4.6 → GPT-4o-mini → Mistral
    """
    global _llm_cache
    if _llm_cache is not None:
        return _llm_cache
    settings = get_settings()
    _factories = {
        "openai": _make_openai,
        "mistral": _make_mistral,
        "anthropic": _make_anthropic,
    }
    # Build ordered list: configured provider first, then the others
    others = [k for k in ["openai", "mistral", "anthropic"] if k != settings.llm_provider]
    order = [settings.llm_provider] + others

    for provider in order:
        try:
            llm = _factories[provider](settings)
            if provider != settings.llm_provider:
                logger.warning("Primary LLM '%s' unavailable — using '%s'", settings.llm_provider, provider)
            _llm_cache = llm
            return _llm_cache
        except Exception as exc:
            logger.warning("LLM provider '%s' failed to initialise: %s", provider, exc)

    raise RuntimeError("No LLM provider could be initialised. Check your API keys.")


# ---------------------------------------------------------------------------
# Node 1: greet
# ---------------------------------------------------------------------------

def greet(state: AgentState) -> dict:
    """
    Fresh session  → send greeting, END (wait for user's first message).
    Returning session → pass through to the node stored in state['next'].
    This prevents re-greeting and stops collect_slots running with no user input.
    """
    if state.get("messages"):
        # Returning session — honour the resume node set by chat.py
        return {"next": state.get("next") or "collect_slots"}
    # First ever call — greet and stop; next HTTP request will carry the user's reply
    return {
        "messages": [AIMessage(content=GREETING_MESSAGE)],
        "next": "END",
    }


# ---------------------------------------------------------------------------
# Node 2: collect_slots
# ---------------------------------------------------------------------------

def _trim_to_last_human(messages: list) -> list:
    """
    Return messages up to and including the last HumanMessage.
    Mistral (and most LLMs) require the conversation to end with a user turn.
    """
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            return messages[: i + 1]
    return []


def collect_slots(state: AgentState) -> dict:
    """GPT-4o with extract_slots tool — loops until phone + amount captured."""
    llm = _get_llm().bind_tools([extract_slots])

    system_content = COLLECT_SLOTS_PROMPT.format(
        system=SYSTEM_PROMPT,
        phone_number=state.get("phone_number") or "not provided yet",
        amount=state.get("amount") or "not provided yet",
    )

    trimmed = _trim_to_last_human(list(state["messages"]))
    if not trimmed:
        # No user input yet — graph should not have reached here; bail safely
        return {"next": "END"}

    msgs = [SystemMessage(content=system_content)] + trimmed
    response: AIMessage = llm.invoke(msgs)

    updates: dict[str, Any] = {"messages": [response]}

    # Check if the LLM called extract_slots
    if response.tool_calls:
        tool_call = response.tool_calls[0]
        tool_result = extract_slots.invoke(tool_call["args"])
        tool_msg = ToolMessage(
            content=json.dumps(tool_result),
            tool_call_id=tool_call["id"],
        )
        updates["messages"] = [response, tool_msg]
        updates["phone_number"] = tool_result.get("phone_number")
        updates["amount"] = float(tool_result.get("amount", 0))
        updates["next"] = "validate"
    else:
        # LLM replied with text (asking for more info) — end this invocation.
        # The bot's question is now in messages; the next HTTP request continues.
        updates["next"] = "END"

    return updates


# ---------------------------------------------------------------------------
# Node 3: validate
# ---------------------------------------------------------------------------

def validate(state: AgentState) -> dict:
    """Fully deterministic validation — no LLM."""
    settings = get_settings()
    phone = state.get("phone_number", "")
    amount = state.get("amount", 0.0)
    errors = []

    # Phone format
    if not phone or not is_valid_nigerian_number(phone):
        errors.append(
            f"The phone number '{phone}' is not a valid 11-digit Nigerian mobile number."
        )

    # Amount range
    if amount < settings.min_topup or amount > settings.max_topup:
        errors.append(
            f"Amount ₦{amount} is outside the allowed range "
            f"(₦{settings.min_topup}–₦{settings.max_topup})."
        )

    if errors:
        error_text = "\n".join(f"• {e}" for e in errors)
        msg = VALIDATION_ERROR_TEMPLATE.format(error=error_text)
        return {
            "messages": [AIMessage(content=msg)],
            "next": "END",
            "phone_number": None if not is_valid_nigerian_number(phone) else phone,
            "amount": None if amount < settings.min_topup or amount > settings.max_topup else amount,
        }

    # Detect network
    network = detect_network(phone)

    # Use the validated phone number as the canonical identifier for cap tracking.
    # For WhatsApp, identifier is already the phone number; for web, this ties the
    # lifetime cap to the recipient number rather than the ephemeral session_id,
    # so the same number can't receive multiple top-ups across different sessions.
    channel = state.get("channel", "web")
    user = db.get_or_create_user(phone, channel)
    user_total = float(user["total_received"])
    remaining = settings.user_lifetime_cap - user_total

    # Cap check
    if user_total >= settings.user_lifetime_cap:
        msg = CAP_EXCEEDED_TEMPLATE.format(total_received=user_total)
        return {
            "messages": [AIMessage(content=msg)],
            "next": "respond",
            "vtu_status": "cap_exceeded",
            "identifier": phone,
            "user_id": user["id"],
            "user_total": user_total,
        }

    if amount > remaining:
        errors.append(
            f"You can only receive ₦{remaining:.0f} more (lifetime cap: ₦{settings.user_lifetime_cap})."
        )
        error_text = "\n".join(f"• {e}" for e in errors)
        msg = VALIDATION_ERROR_TEMPLATE.format(error=error_text)
        return {
            "messages": [AIMessage(content=msg)],
            "next": "END",
            "amount": None,
            "identifier": phone,
            "user_id": user["id"],
            "user_total": user_total,
        }

    return {
        "network": network,
        "identifier": phone,
        "user_id": user["id"],
        "user_total": user_total,
        "next": "confirm",
    }


# ---------------------------------------------------------------------------
# Node 4: confirm
# ---------------------------------------------------------------------------

def confirm(state: AgentState) -> dict:
    """GPT-4o with confirm_or_reject tool — present summary and await user decision."""
    llm = _get_llm().bind_tools([confirm_or_reject])

    system_content = CONFIRM_PROMPT.format(
        system=SYSTEM_PROMPT,
        phone_number=state.get("phone_number"),
        network=state.get("network"),
        amount=state.get("amount"),
    )

    trimmed = _trim_to_last_human(list(state["messages"]))
    if not trimmed:
        return {"next": "END"}

    msgs = [SystemMessage(content=system_content)] + trimmed
    response: AIMessage = llm.invoke(msgs)

    updates: dict[str, Any] = {"messages": [response]}

    if response.tool_calls:
        tool_call = response.tool_calls[0]
        tool_result = confirm_or_reject.invoke(tool_call["args"])
        tool_msg = ToolMessage(
            content=json.dumps(tool_result),
            tool_call_id=tool_call["id"],
        )
        updates["messages"] = [response, tool_msg]
        confirmed = tool_result.get("confirmed", False)
        updates["confirmed"] = confirmed
        updates["next"] = "execute" if confirmed else "collect_slots"
        if not confirmed:
            # Reset slots so user can re-enter
            updates["phone_number"] = None
            updates["amount"] = None
            updates["network"] = None
    else:
        # LLM presented the summary — end this invocation and wait for user's yes/no.
        # "confirm" is stored in session state so the next HTTP request resumes here.
        updates["next"] = "END"

    return updates


# ---------------------------------------------------------------------------
# Node 5: execute
# ---------------------------------------------------------------------------

async def execute(state: AgentState) -> dict:
    """Call VTU dispatcher, log to DB, trigger notifier if needed."""
    settings = get_settings()
    phone = state["phone_number"]
    network = state["network"]
    amount = state["amount"]
    user_id = state["user_id"]
    session_id = state.get("session_id", "unknown")

    idempotency_key = generate_idempotency_key(session_id, phone, amount)

    # Check for existing transaction with this key (idempotency guard)
    existing = db.get_transaction_by_idempotency_key(idempotency_key)
    if existing:
        if existing["status"] == "success":
            # Already disbursed — return cached result, do not charge again
            logger.warning("Duplicate request for key %s — returning cached success", idempotency_key)
            return {
                "tx_id": existing["id"],
                "idempotency_key": idempotency_key,
                "vtu_status": "success",
                "next": "respond",
            }
        # pending or failed — reuse the existing row for the retry attempt
        logger.info("Retrying existing %s transaction %s", existing["status"], existing["id"])
        tx_id = existing["id"]
        # Reset to pending so the outcome is re-evaluated
        db.update_transaction_status(tx_id, "pending")
    else:
        # Brand-new transaction
        tx = db.create_transaction(user_id, phone, network, amount, idempotency_key)
        tx_id = tx["id"]

    # Disburse
    result = await vtu_dispatcher.disburse(phone, network, amount, idempotency_key)

    if result["success"]:
        db.update_transaction_status(tx_id, "success", result["reference"], result["raw"])
        db.increment_user_total(user_id, amount)

        # Wallet snapshot + low-balance check
        try:
            raw_balance = result["raw"].get("content", {}).get("transactions", {}).get("current_balance")
            if raw_balance is not None:
                balance = float(raw_balance)
                db.save_wallet_snapshot(balance)
                if balance < settings.low_balance_threshold:
                    import asyncio
                    asyncio.create_task(send_low_balance_alert(balance))
        except Exception as exc:
            logger.warning("Wallet snapshot failed: %s", exc)

        return {
            "tx_id": tx_id,
            "idempotency_key": idempotency_key,
            "vtu_status": "success",
            "next": "respond",
            "messages": [AIMessage(content=f"_VTU disbursement success via {result['provider']}_")],
        }
    else:
        db.update_transaction_status(tx_id, "failed", result.get("reference"), result.get("raw"))
        return {
            "tx_id": tx_id,
            "idempotency_key": idempotency_key,
            "vtu_status": "failed",
            "error_message": str(result.get("raw", {}).get("error", "Unknown VTU error")),
            "next": "respond",
        }


# ---------------------------------------------------------------------------
# Node 6: respond
# ---------------------------------------------------------------------------

def respond(state: AgentState) -> dict:
    """Pre-written response templates — no LLM."""
    vtu_status = state.get("vtu_status")
    phone = state.get("phone_number", "N/A")
    network = state.get("network", "N/A")
    amount = state.get("amount", 0)

    if vtu_status == "success":
        reference = state.get("idempotency_key", "N/A")[:12] + "..."
        msg = SUCCESS_TEMPLATE.format(
            amount=amount,
            phone_number=phone,
            network=network,
            reference=reference,
        )
        return {
            "messages": [AIMessage(content=msg)],
            "next": "END",
        }

    if vtu_status == "cap_exceeded":
        user_total = state.get("user_total", 500)
        msg = CAP_EXCEEDED_TEMPLATE.format(total_received=user_total)
        return {
            "messages": [AIMessage(content=msg)],
            "next": "END",
        }

    # Failure — clear vtu_status so the next user message resumes at confirm
    # (chat.py sees slots still populated → resume_at="confirm") and retries cleanly.
    msg = FAILURE_TEMPLATE.format(amount=amount, phone_number=phone)
    return {
        "messages": [AIMessage(content=msg)],
        "vtu_status": None,
        "error_message": None,
        "next": "END",
    }
