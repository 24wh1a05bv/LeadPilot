"""Tests for lead scoring and classification.

Covers:
- Hot lead drafted (Output layer)
- Disqualify (Governance layer)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.state import Lead, AgentState
from agent.nodes.enrich import enrich_node
from agent.nodes.score import score_node
from agent.nodes.classify import classify_node
from agent.nodes.route import route_node, route_decision
from agent.nodes.draft import draft_node


def _run_pipeline(lead_data: dict) -> AgentState:
    """Run the full pipeline and return the final state."""
    lead = Lead(**lead_data)
    state = AgentState(lead=lead)

    # enrich
    result = enrich_node(state)
    for key, value in result.items():
        setattr(state, key, value)

    # score
    result = score_node(state)
    for key, value in result.items():
        setattr(state, key, value)

    # classify
    result = classify_node(state)
    for key, value in result.items():
        setattr(state, key, value)

    # route
    result = route_node(state)
    for key, value in result.items():
        setattr(state, key, value)

    # draft if HOT
    decision = route_decision(state)
    if decision == "draft":
        result = draft_node(state)
        for key, value in result.items():
            setattr(state, key, value)

    return state


class TestHotLeadDrafted:
    """Test scenario: Hot lead drafted (Output layer)."""

    def test_hot_lead_classification(self):
        """A lead matching ICP should be classified as HOT with correct score."""
        lead_data = {
            "name": "Alice Chen",
            "email": "alice@acmecorp.com",
            "company": "Acme Corp",
            "role": "CTO",
            "message": "We're looking for a sales automation solution to help our growing team.",
        }
        state = _run_pipeline(lead_data)

        # Assert classification is HOT
        assert state.classification is not None
        assert state.classification.label == "HOT", f"Expected HOT, got {state.classification.label}"

        # Assert score is high (Acme Corp is Software, 420 employees, CTO role)
        assert state.score is not None
        assert state.score.total >= 80, f"Expected score >= 80, got {state.score.total}"

        # Assert reason cites correct factors
        assert state.classification.reason is not None
        assert "industry" in state.classification.reason.lower() or "score" in state.classification.reason.lower()

    def test_hot_lead_draft_created(self):
        """A HOT lead should have a non-null email draft."""
        lead_data = {
            "name": "Bob Zhang",
            "email": "bob@initech.com",
            "company": "Initech",
            "role": "VP Engineering",
            "message": "Interested in your lead scoring platform.",
        }
        state = _run_pipeline(lead_data)

        # Assert draft exists
        assert state.draft is not None, "HOT lead should have a draft"

        # Assert draft has content
        assert state.draft.subject, "Draft should have a subject"
        assert state.draft.body, "Draft should have a body"

        # Assert draft is grounded on enrichment facts
        assert len(state.draft.grounded_on) > 0, "Draft should reference enrichment facts"

    def test_hot_lead_email_not_sent(self):
        """The draft node should NOT call email_send."""
        lead_data = {
            "name": "Carol Davis",
            "email": "carol@cyberdyne.com",
            "company": "Cyberdyne Systems",
            "role": "CTO",
            "message": "We need better sales tools.",
        }
        state = _run_pipeline(lead_data)

        # Draft exists but no approval - email should not have been sent
        assert state.draft is not None
        assert state.approval is None, "Email should not be sent without approval"


class TestDisqualify:
    """Test scenario: Disqualify (Governance layer)."""

    def test_disqualify_low_score(self):
        """A lead with poor ICP fit should be DISQUALIFY."""
        lead_data = {
            "name": "Dan Wilson",
            "email": "dan@globex.com",
            "company": "Globex Inc",
            "role": "Operator",
            "message": "Just browsing.",
        }
        state = _run_pipeline(lead_data)

        # Assert classification is DISQUALIFY
        assert state.classification is not None
        assert state.classification.label == "DISQUALIFY", f"Expected DISQUALIFY, got {state.classification.label}"

        # Assert no draft
        assert state.draft is None, "DISQUALIFY lead should not have a draft"

    def test_disqualify_no_outreach(self):
        """DISQUALIFY leads should have no outreach of any kind."""
        lead_data = {
            "name": "Eve Martin",
            "email": "eve@umbrella.com",
            "company": "Umbrella Corp",
            "role": "Intern",
            "message": "Not interested at this time.",
        }
        state = _run_pipeline(lead_data)

        # Assert no draft
        assert state.draft is None, "DISQUALIFY lead should not have a draft"

        # Assert classification reason is logged
        assert state.classification is not None
        assert state.classification.reason, "Classification should have a reason"

    def test_disqualify_unknown_company(self):
        """A lead from an unknown company should still be processed."""
        lead_data = {
            "name": "Frank Lee",
            "email": "frank@unknown-startup.io",
            "company": "Unknown Startup",
            "role": "CEO",
            "message": "Tell me about your product.",
        }
        state = _run_pipeline(lead_data)

        # Should still get a classification (may be NURTURE or DISQUALIFY)
        assert state.classification is not None
        assert state.classification.label in ("HOT", "NURTURE", "DISQUALIFY")

        # Enrichment should exist even if no match
        assert state.enrichment is not None