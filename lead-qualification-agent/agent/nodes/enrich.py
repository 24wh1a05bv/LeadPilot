"""Enrichment node - looks up company data for an incoming lead."""

from __future__ import annotations

from datetime import datetime

from agent.state import AgentState, Enrichment
from tools.enrichment_lookup import enrichment_lookup


def enrich_node(state: AgentState) -> dict:
    """Enrich a lead with company data from the lookup tool.

    Args:
        state: Current agent state with lead information.

    Returns:
        Dict with updated enrichment and audit trail entry.
    """
    lead = state.lead
    enrichment: Enrichment | None = enrichment_lookup(lead.company)

    if enrichment is None:
        # Fallback: create minimal enrichment for unknown companies
        enrichment = Enrichment(
            industry=None,
            employee_count=None,
            revenue_estimate=None,
            tech_stack=[],
            buying_signal=None,
            source="no match found",
        )

    audit_entry = {
        "node": "enrich",
        "timestamp": datetime.now().isoformat(),
        "input": {"company": lead.company},
        "output": enrichment.model_dump(),
    }

    return {
        "enrichment": enrichment,
        "audit_trail": [audit_entry],
    }