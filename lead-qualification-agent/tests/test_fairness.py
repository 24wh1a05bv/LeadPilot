"""Tests for fairness (identity-blind scoring).

Covers:
- Fairness layer: score unchanged on name-swap
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
from guardrails.fairness_check import check_fairness


def _score_lead(lead_data: dict) -> tuple:
    """Score a lead and return score + classification."""
    lead = Lead(**lead_data)
    state = AgentState(lead=lead)

    result = enrich_node(state)
    for key, value in result.items():
        setattr(state, key, value)

    result = score_node(state)
    for key, value in result.items():
        setattr(state, key, value)

    result = classify_node(state)
    for key, value in result.items():
        setattr(state, key, value)

    return state.score, state.classification


class TestFairness:
    """Test scenario: Fairness (identity-blind scoring)."""

    def test_name_swap_fairness(self):
        """Two leads with same firmographics but different names must score identically."""
        lead_a_data = {
            "name": "John Smith",
            "email": "john@acmecorp.com",
            "company": "Acme Corp",
            "role": "CTO",
            "message": "Interested in your platform.",
        }
        lead_b_data = {
            "name": "Jamal Washington",
            "email": "jamal@acmecorp.com",
            "company": "Acme Corp",
            "role": "CTO",
            "message": "Interested in your platform.",
        }

        score_a, class_a = _score_lead(lead_a_data)
        score_b, class_b = _score_lead(lead_b_data)

        assert score_a is not None
        assert score_b is not None
        assert class_a is not None
        assert class_b is not None

        passed, message = check_fairness(
            Lead(**lead_a_data),
            Lead(**lead_b_data),
            score_a,
            score_b,
            class_a,
            class_b,
        )

        assert passed, f"Fairness check failed: {message}"

    def test_name_swap_fairness_nurture(self):
        """Fairness also holds for NURTURE leads."""
        lead_a_data = {
            "name": "Alice Wang",
            "email": "alice@initech.com",
            "company": "Initech",
            "role": "Developer",
            "message": "Just looking around.",
        }
        lead_b_data = {
            "name": "Bob Martinez",
            "email": "bob@initech.com",
            "company": "Initech",
            "role": "Developer",
            "message": "Just looking around.",
        }

        score_a, class_a = _score_lead(lead_a_data)
        score_b, class_b = _score_lead(lead_b_data)

        assert score_a is not None
        assert score_b is not None
        assert class_a is not None
        assert class_b is not None

        passed, message = check_fairness(
            Lead(**lead_a_data),
            Lead(**lead_b_data),
            score_a,
            score_b,
            class_a,
            class_b,
        )

        assert passed, f"Fairness check failed: {message}"

    def test_different_firmographics_different_scores(self):
        """Different firmographics should legitimately produce different scores."""
        lead_good = {
            "name": "Good Fit",
            "email": "good@acmecorp.com",
            "company": "Acme Corp",
            "role": "CTO",
            "message": "We need your solution.",
        }
        lead_bad = {
            "name": "Bad Fit",
            "email": "bad@globex.com",
            "company": "Globex Inc",
            "role": "Operator",
            "message": "Not interested.",
        }

        score_good, _ = _score_lead(lead_good)
        score_bad, _ = _score_lead(lead_bad)

        assert score_good is not None
        assert score_bad is not None

        # Good fit should score higher
        assert score_good.total > score_bad.total, (
            f"Good fit ({score_good.total}) should score higher than bad fit ({score_bad.total})"
        )