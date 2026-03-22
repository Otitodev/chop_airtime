"""
Test that validate node never loops back to collect_slots synchronously.
This guards against the infinite LLM call loop bug.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage

mock_settings = MagicMock()
mock_settings.min_topup = 50.0
mock_settings.max_topup = 500.0
mock_settings.user_lifetime_cap = 500.0

with patch("config.get_settings", return_value=mock_settings), \
     patch("database.get_or_create_user", return_value={"id": "u1", "total_received": 0}):
    from agent.nodes import validate


def _base_state(**overrides):
    state = {
        "messages": [HumanMessage(content="top up 08031234567 with 200")],
        "session_id": "test-session",
        "channel": "web",
        "identifier": "test-session",
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
    state.update(overrides)
    return state


def test_invalid_phone_goes_to_END():
    state = _base_state(phone_number="12345", amount=200.0)
    with patch("config.get_settings", return_value=mock_settings):
        result = validate(state)
    assert result["next"] == "END", f"Expected END, got {result['next']}"
    print("PASS  invalid phone -> next=END (no loop)")


def test_invalid_amount_goes_to_END():
    state = _base_state(phone_number="08031234567", amount=10.0)
    with patch("config.get_settings", return_value=mock_settings):
        result = validate(state)
    assert result["next"] == "END", f"Expected END, got {result['next']}"
    print("PASS  amount below min -> next=END (no loop)")


def test_amount_above_max_goes_to_END():
    state = _base_state(phone_number="08031234567", amount=600.0)
    with patch("config.get_settings", return_value=mock_settings):
        result = validate(state)
    assert result["next"] == "END", f"Expected END, got {result['next']}"
    print("PASS  amount above max -> next=END (no loop)")


def test_cap_exceeded_goes_to_respond():
    state = _base_state(phone_number="08031234567", amount=200.0)
    with patch("config.get_settings", return_value=mock_settings), \
         patch("database.get_or_create_user", return_value={"id": "u1", "total_received": 500}):
        result = validate(state)
    assert result["next"] == "respond", f"Expected respond, got {result['next']}"
    print("PASS  cap exceeded -> next=respond")


def test_amount_over_remaining_goes_to_END():
    state = _base_state(phone_number="08031234567", amount=400.0)
    with patch("config.get_settings", return_value=mock_settings), \
         patch("database.get_or_create_user", return_value={"id": "u1", "total_received": 200}):
        result = validate(state)
    assert result["next"] == "END", f"Expected END, got {result['next']}"
    print("PASS  amount over remaining cap -> next=END (no loop)")


def test_valid_input_goes_to_confirm():
    state = _base_state(phone_number="08031234567", amount=200.0)
    with patch("config.get_settings", return_value=mock_settings), \
         patch("database.get_or_create_user", return_value={"id": "u1", "total_received": 0}):
        result = validate(state)
    assert result["next"] == "confirm", f"Expected confirm, got {result['next']}"
    print("PASS  valid input -> next=confirm")


def test_no_collect_slots_in_any_error_path():
    """Regression: validate must NEVER return next='collect_slots'."""
    cases = [
        _base_state(phone_number="bad", amount=200.0),
        _base_state(phone_number="08031234567", amount=10.0),
        _base_state(phone_number="08031234567", amount=600.0),
        _base_state(phone_number="", amount=0.0),
    ]
    for state in cases:
        with patch("config.get_settings", return_value=mock_settings), \
             patch("database.get_or_create_user", return_value={"id": "u1", "total_received": 0}):
            result = validate(state)
        assert result["next"] != "collect_slots", (
            f"BUG: validate returned collect_slots -- infinite loop risk! phone={state['phone_number']} amount={state['amount']}"
        )
    print("PASS  validate never returns collect_slots on any error path")


if __name__ == "__main__":
    tests = [
        test_invalid_phone_goes_to_END,
        test_invalid_amount_goes_to_END,
        test_amount_above_max_goes_to_END,
        test_cap_exceeded_goes_to_respond,
        test_amount_over_remaining_goes_to_END,
        test_valid_input_goes_to_confirm,
        test_no_collect_slots_in_any_error_path,
    ]
    failures = []
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"FAIL  {t.__name__}: {e}")
            failures.append(t.__name__)

    print(f"\n{'='*50}")
    print(f"Results: {len(tests) - len(failures)}/{len(tests)} passed")
    if failures:
        print(f"Failed: {failures}")
        sys.exit(1)
    else:
        print("All tests passed.")
