"""Pydantic request/response models for FastAPI routes."""

from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Unique session identifier for web users")
    message: str = Field(..., description="User's message text")


class ChatResponse(BaseModel):
    session_id: str
    reply: str


class WhatsAppMessage(BaseModel):
    """Simplified representation of an inbound Evolution API webhook payload."""
    from_number: str
    message: str
    message_id: str


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
