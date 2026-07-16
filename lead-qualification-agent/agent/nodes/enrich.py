"""Enrichment node - looks up company data for an incoming lead.

Uses a fallback chain:
1. Mock database (fast, free, high confidence)
2. DuckDuckGo web search + LLM extraction (slower, lower confidence)
"""

from __future__ import annotations

from agent.llm import LLM
from agent.state import AgentState, Enrichment
from agent.timestamps import next_timestamp
from tools.enrichment_lookup import enrichment_lookup
from tools.web_search_enrich import web_search_enrich


def enrich_node(state: AgentState) -> dict:
    """Enrich a lead with company data using fallback chain.

    Tries mock database first, then falls back to web search if not found.

    Args:
        state: Current agent state with lead information.

    Returns:
        Dict with updated enrichment and audit trail entry.
    """
    lead = state.lead
    enrichment: Enrichment | None = None
    source = ""

    # Step 1: Try mock database (fast, high confidence)
    enrichment = enrichment_lookup(lead.company)

    if enrichment is not None:
        enrichment.confidence = "high"
        enrichment.source_reliability = "high"
        enrichment.unknown_factors = []
        source = f"mock_db: {enrichment.source}"
    else:
        # Step 2: Fallback to web search (slower, lower confidence)
        llm = LLM(temperature=0.0)
        enrichment = web_search_enrich(
            company=lead.company,
            email=lead.email,
            llm=llm,
        )
        source = f"web_search: {enrichment.source}"

    audit_entry = {
        "node": "enrich",
        "timestamp": next_timestamp(state),
        "input": {"company": lead.company},
        "output": enrichment.model_dump(),
    }

    return {
        "enrichment": enrichment,
        "audit_trail": [audit_entry],
    }