"""Classification node - classifies a lead as HOT, NURTURE, or DISQUALIFY."""

from __future__ import annotations

import json
from pathlib import Path

from agent.state import AgentState, Classification
from agent.timestamps import next_timestamp


def _load_icp_config() -> dict:
    """Load ICP configuration from JSON."""
    config_path = Path(__file__).parent.parent.parent / "data" / "icp_config.json"
    with open(config_path) as f:
        return json.load(f)


def classify_node(state: AgentState) -> dict:
    """Classify a lead based on its score.

    Uses configurable thresholds from icp_config.json.
    90+ HOT, 50-89 NURTURE, <50 DISQUALIFY (configurable).

    Args:
        state: Current agent state with score breakdown.

    Returns:
        Dict with updated classification and audit trail entry.
    """
    config = _load_icp_config()
    thresholds = config["thresholds"]
    hot_min = thresholds["hot_min"]
    nurture_min = thresholds["nurture_min"]

    score = state.score
    if score is None:
        classification = Classification(
            label="DISQUALIFY",
            reason="No score available - cannot classify."
        )
    else:
        total = score.total
        if total >= hot_min:
            label = "HOT"
        elif total >= nurture_min:
            label = "NURTURE"
        else:
            label = "DISQUALIFY"

        # Build a cited reason referencing specific score factors
        factors = []
        if score.industry_match > 0:
            factors.append(f"industry match ({score.industry_match} pts)")
        if score.company_size > 0:
            factors.append(f"company size ({score.company_size} pts)")
        if score.role_match > 0:
            factors.append(f"role match ({score.role_match} pts)")
        if score.buying_signal > 0:
            factors.append(f"buying signal ({score.buying_signal} pts)")

        if factors:
            reason = f"Score {total}/100: {', '.join(factors)}."
        else:
            reason = f"Score {total}/100: no matching criteria met."

        classification = Classification(label=label, reason=reason)

    audit_entry = {
        "node": "classify",
        "timestamp": next_timestamp(state),
        "input": {"score_total": score.total if score else None},
        "output": classification.model_dump(),
    }

    return {
        "classification": classification,
        "audit_trail": [audit_entry],
    }