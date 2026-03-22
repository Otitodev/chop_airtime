"""LangGraph StateGraph wiring for the Chop Airtime agent."""

from __future__ import annotations

from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.nodes import greet, collect_slots, validate, confirm, execute, respond


def _route(state: AgentState) -> str:
    """Conditional edge router — reads state['next']."""
    return state.get("next", END)


def build_graph():
    """Build and compile the Chop Airtime LangGraph StateGraph."""
    builder = StateGraph(AgentState)

    builder.add_node("greet", greet)
    builder.add_node("collect_slots", collect_slots)
    builder.add_node("validate", validate)
    builder.add_node("confirm", confirm)
    builder.add_node("execute", execute)
    builder.add_node("respond", respond)

    builder.set_entry_point("greet")

    # greet can go to END (fresh session) or resume at any node (returning session)
    builder.add_conditional_edges(
        "greet",
        _route,
        {
            "END": END,
            "collect_slots": "collect_slots",
            "confirm": "confirm",
            "execute": "execute",
            "respond": "respond",
        },
    )

    # collect_slots loops, advances to validate, or exits cleanly
    builder.add_conditional_edges(
        "collect_slots",
        _route,
        {
            "collect_slots": "collect_slots",
            "validate": "validate",
            "END": END,
        },
    )

    builder.add_conditional_edges(
        "validate",
        _route,
        {
            "confirm": "confirm",
            "collect_slots": "collect_slots",
            "respond": "respond",
            "END": END,
        },
    )

    # confirm loops, advances to execute, falls back to collect_slots, or exits
    builder.add_conditional_edges(
        "confirm",
        _route,
        {
            "confirm": "confirm",
            "execute": "execute",
            "collect_slots": "collect_slots",
            "END": END,
        },
    )

    builder.add_conditional_edges("execute", _route, {"respond": "respond"})
    builder.add_conditional_edges("respond", _route, {"END": END})

    return builder.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
