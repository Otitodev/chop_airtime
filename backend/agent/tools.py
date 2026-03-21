"""LangChain tool definitions for slot extraction and confirmation."""

from __future__ import annotations

from typing import Optional
from langchain_core.tools import tool


@tool
def extract_slots(phone_number: str, amount: float) -> dict:
    """
    Call this tool when you have collected BOTH the phone number and the amount from the user.

    Args:
        phone_number: 11-digit Nigerian phone number starting with 0 (e.g. '08031234567').
        amount: Top-up amount in Naira. Must be between 50 and 500.

    Returns:
        A dict confirming the extracted values.
    """
    return {"phone_number": phone_number, "amount": amount}


@tool
def confirm_or_reject(confirmed: bool) -> dict:
    """
    Call this tool once the user has explicitly confirmed or rejected the top-up summary.

    Args:
        confirmed: True if the user agreed to proceed, False if they want to change details.

    Returns:
        A dict with the confirmation status.
    """
    return {"confirmed": confirmed}
