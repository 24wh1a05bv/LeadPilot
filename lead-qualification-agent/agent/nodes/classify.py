"""Classification node - classifies a lead as HOT, NURTURE, DISQUALIFY, or MANUAL_REVIEW."""

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
    """Classify a lead based on its score and confidence.

    Classification matrix:
        Score >= 80 + High confidence  → HOT
        Score >= 80 + Medium confidence → HOT (review recommended)
        Score >= 80 + Low confidence   → MANUAL_REVIEW
        Score 50-79 + High/Medium      → NURTURE
        Score 50-79 + Low confidence   → MANUAL_REVIEW
        Score < 50 + Any               → DISQUALIFY

    Low confidence leads never auto-classify as HOT.

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
        confidence = score.confidence
        unknown_factors = score.unknown_factors

        # Build cited reason first
        factors = []
        if score.industry_match > 0:
            factors.append(f"industry match ({score.industry_match} pts)")
        else:
            # Check if industry was known but not in ICP
            enrichment = state.enrichment
            if enrichment and enrichment.industry:
                factors.append(f"industry not in target profile ({score.industry_actual})")
            else:
                factors.append("industry unknown")
        if score.company_size > 0:
            factors.append(f"company size ({score.company_size} pts)")
        else:
            factors.append("company size unknown")
        if score.role_match > 0:
            factors.append(f"role match ({score.role_match} pts)")
        if score.buying_signal > 0:
            factors.append(f"buying signal ({score.buying_signal} pts)")

        factors_str = ", ".join(factors) if factors else "no matching criteria"

        # Classification matrix
        if total >= hot_min:
            if confidence == "high":
                label = "HOT"
                reason = f"Score {total}/100 (high confidence): {factors_str}."
            elif confidence == "medium":
                label = "HOT"
                reason = (
                    f"Score {total}/100 (medium confidence): {factors_str}. "
                    f"Review recommended before outreach."
                )
            else:  # low confidence
                label = "MANUAL_REVIEW"
                reason = (
                    f"Score {total}/100 but low confidence. "
                    f"Unknown factors: {', '.join(unknown_factors)}. "
                    f"Insufficient verified data for automatic HOT classification."
                )
        elif total >= nurture_min:
            if confidence == "low":
                label = "MANUAL_REVIEW"
                reason = (
                    f"Score {total}/100 with low confidence. "
                    f"Unknown factors: {', '.join(unknown_factors)}. "
                    f"Needs manual verification."
                )
            else:
                label = "NURTURE"
                reason = f"Score {total}/100 ({confidence} confidence): {factors_str}."
        else:
            label = "DISQUALIFY"
            reason = f"Score {total}/100: {factors_str}."

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