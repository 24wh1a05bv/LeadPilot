"""Routing node - determines the next step based on classification."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from agent.state import AgentState
from tools.crm_write import crm_write


def route_node(state: AgentState) -> dict:
    """Route the lead based on its classification.

    HOT leads proceed to the draft node.
    NURTURE leads are enrolled in a nurture sequence.
    DISQUALIFY leads are archived.

    Args:
        state: Current agent state with classification.

    Returns:
        Dict with routing decision and audit trail entry.
    """
    classification = state.classification
    lead = state.lead

    decision: str = classification.label if classification else "DISQUALIFY"
    reason: str = classification.reason if classification else "No classification available"

    # Log routing action to CRM/audit log
    if decision == "NURTURE":
        crm_write(
            lead_id=lead.email,
            status="nurture",
            reason=reason,
            lead_name=lead.name,
            lead_email=lead.email,
            lead_company=lead.company,
        )
    elif decision == "DISQUALIFY":
        crm_write(
            lead_id=lead.email,
            status="disqualified",
            reason=reason,
            lead_name=lead.name,
            lead_email=lead.email,
            lead_company=lead.company,
        )

    audit_entry = {
        "node": "route",
        "timestamp": datetime.now().isoformat(),
        "input": {"classification": decision, "reason": reason},
        "output": {"decision": decision, "routed_to": "draft" if decision == "HOT" else decision.lower()},
    }

    return {
        "audit_trail": [audit_entry],
    }


def route_decision(state: AgentState) -> Literal["draft", "enroll_sequence", "archive"]:
    """Conditional edge function - determines which branch to take.

    Args:
        state: Current agent state.

    Returns:
        Next node name based on classification.
    """
    if state.classification is None:
        return "archive"

    label = state.classification.label
    if label == "HOT":
        return "draft"
    elif label == "NURTURE":
        return "enroll_sequence"
    else:
        return "archive"