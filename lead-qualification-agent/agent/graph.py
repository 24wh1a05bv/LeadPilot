"""LangGraph StateGraph definition for the Lead Qualification Agent.

Pipeline: START -> enrich -> score -> classify -> route -> [draft] -> [human_gate] -> END
                                    |                    |
                                    +-> NURTURE -> enroll_sequence -> END
                                    +-> DISQUALIFY -> archive -> END
"""

from __future__ import annotations

from typing import Any

from agent.state import AgentState, ApprovalDecision
from agent.nodes.enrich import enrich_node
from agent.nodes.score import score_node
from agent.nodes.classify import classify_node
from agent.nodes.route import route_node, route_decision
from agent.nodes.draft import draft_node
from tools.crm_write import crm_write
from tools.email_send import email_send


def create_graph() -> Any:
    """Create the LangGraph StateGraph for lead qualification.

    Returns:
        A compiled LangGraph StateGraph application.

    Note: This function attempts to use LangGraph. If langgraph is not
    installed, it falls back to a simple sequential pipeline.
    """
    try:
        return _create_langgraph()
    except ImportError:
        return _create_simple_pipeline()


def _create_langgraph():
    """Create the graph using LangGraph."""
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint import MemorySaver

    # Define the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("enrich", enrich_node)
    workflow.add_node("score", score_node)
    workflow.add_node("classify", classify_node)
    workflow.add_node("route", route_node)
    workflow.add_node("draft", draft_node)
    workflow.add_node("enroll_sequence", _enroll_sequence_node)
    workflow.add_node("archive", _archive_node)
    workflow.add_node("human_gate", _human_gate_node)
    workflow.add_node("send_email", _send_email_node)

    # Add edges
    workflow.set_entry_point("enrich")
    workflow.add_edge("enrich", "score")
    workflow.add_edge("score", "classify")
    workflow.add_edge("classify", "route")

    # Conditional routing after route
    workflow.add_conditional_edges(
        "route",
        route_decision,
        {
            "draft": "draft",
            "enroll_sequence": "enroll_sequence",
            "archive": "archive",
        }
    )

    # After draft, go to human gate
    workflow.add_edge("draft", "human_gate")

    # Terminal nodes
    workflow.add_edge("enroll_sequence", END)
    workflow.add_edge("archive", END)
    workflow.add_edge("send_email", END)

    # Human gate: after approval, either send or archive
    workflow.add_conditional_edges(
        "human_gate",
        _gate_decision,
        {
            "send_email": "send_email",
            "archive": "archive",
        }
    )

    # Compile with a checkpointer for interrupt support
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app


def _create_simple_pipeline():
    """Fallback: simple sequential pipeline without LangGraph.

    This is used when LangGraph is not installed. It runs the nodes
    sequentially and handles routing logic manually.
    """
    class SimplePipeline:
        """Simple sequential pipeline that mimics the graph."""

        def __init__(self):
            self.checkpointer = None

        def invoke(self, input_data: dict, config: dict | None = None) -> dict:
            """Run the pipeline sequentially."""
            state = AgentState(**input_data)

            # enrich
            result = enrich_node(state)
            for key, value in result.items():
                if key == "audit_trail":
                    state.audit_trail.extend(value)
                else:
                    setattr(state, key, value)

            # score
            result = score_node(state)
            for key, value in result.items():
                if key == "audit_trail":
                    state.audit_trail.extend(value)
                else:
                    setattr(state, key, value)

            # classify
            result = classify_node(state)
            for key, value in result.items():
                if key == "audit_trail":
                    state.audit_trail.extend(value)
                else:
                    setattr(state, key, value)

            # route
            result = route_node(state)
            for key, value in result.items():
                if key == "audit_trail":
                    state.audit_trail.extend(value)
                else:
                    setattr(state, key, value)

            # routing decision
            decision = route_decision(state)

            if decision == "draft":
                result = draft_node(state)
                for key, value in result.items():
                    if key == "audit_trail":
                        state.audit_trail.extend(value)
                    else:
                        setattr(state, key, value)
                # Human gate - requires external approval
                # In simple mode, we just return the state for the UI to handle
            elif decision == "enroll_sequence":
                _enroll_sequence_node(state)
            else:
                _archive_node(state)

            return state.model_dump()

        def get_state(self, config: dict) -> dict | None:
            """Get state (stub for compatibility)."""
            return None

        def update_state(self, config: dict, values: dict) -> None:
            """Update state (stub for compatibility)."""
            pass

    return SimplePipeline()


def _enroll_sequence_node(state: AgentState) -> dict:
    """Enroll a NURTURE lead in a nurture sequence."""
    crm_write(
        lead_id=state.lead.email,
        status="nurture_enrolled",
        reason=state.classification.reason if state.classification else "Nurture lead",
        lead_name=state.lead.name,
        lead_email=state.lead.email,
        lead_company=state.lead.company,
    )
    return {}


def _archive_node(state: AgentState) -> dict:
    """Archive a DISQUALIFY lead."""
    crm_write(
        lead_id=state.lead.email,
        status="archived",
        reason=state.classification.reason if state.classification else "Disqualified",
        lead_name=state.lead.name,
        lead_email=state.lead.email,
        lead_company=state.lead.company,
    )
    return {}


def _human_gate_node(state: AgentState) -> dict:
    """Human approval gate - interrupts execution for rep decision.

    This node is where LangGraph's interrupt() would be called.
    In the simple pipeline, this is handled by the UI.
    """
    # In a full LangGraph implementation, this would call interrupt()
    # to pause execution and wait for human input.
    # For now, we just pass through and let the UI handle the gate.
    return {}


def _gate_decision(state: AgentState) -> str:
    """Determine what to do after the human gate.

    Args:
        state: Current agent state with approval decision.

    Returns:
        'send_email' if approved/edited, 'archive' if rejected.
    """
    if state.approval is None:
        return "archive"

    if state.approval.action in ("approve", "edit"):
        return "send_email"
    else:
        return "archive"


def _send_email_node(state: AgentState) -> dict:
    """Send the approved email."""
    if state.draft is None or state.approval is None:
        return {}

    body = state.approval.edited_body if state.approval.edited_body else state.draft.body

    email_send(
        to=state.lead.email,
        subject=state.draft.subject,
        body=body,
        lead_name=state.lead.name,
        lead_company=state.lead.company,
        approval_action=state.approval.action,
    )
    return {}


def run_agent(lead_data: dict, approval: dict | None = None) -> dict:
    """Run the lead qualification agent on a single lead.

    Args:
        lead_data: Dict with lead fields (name, email, company, role, message).
        approval: Optional approval decision dict (action, edited_body, rep_id).

    Returns:
        Final agent state as a dict.
    """
    from agent.state import Lead

    # Create the graph
    app = create_graph()

    # Prepare input
    lead = Lead(**lead_data)
    input_state = {"lead": lead}

    # If approval is provided, include it
    if approval:
        input_state["approval"] = ApprovalDecision(**approval)

    # Run the agent
    result = app.invoke(input_state)

    return result