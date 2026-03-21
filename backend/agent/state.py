"""AgentState TypedDict for the Chop Airtime LangGraph agent."""

from __future__ import annotations

from typing import Optional, Annotated
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # Conversation history (append-only via add_messages reducer)
    messages: Annotated[list[BaseMessage], add_messages]

    # Session / user identity
    session_id: str
    channel: str          # "web" or "whatsapp"
    identifier: str       # session_id for web; phone number for WhatsApp

    # Slots collected during conversation
    phone_number: Optional[str]
    network: Optional[str]
    amount: Optional[float]

    # Database references
    user_id: Optional[str]
    user_total: Optional[float]

    # Flow control
    confirmed: Optional[bool]   # True = user confirmed, False = rejected, None = pending
    tx_id: Optional[str]
    idempotency_key: Optional[str]

    # VTU result
    vtu_status: Optional[str]   # "success" | "failed"
    error_message: Optional[str]

    # Graph routing
    next: Optional[str]
