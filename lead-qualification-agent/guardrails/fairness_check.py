"""Fairness check utility for identity-blind scoring.

Ensures that two leads with identical firmographic data but different
names/emails receive the same score and classification.
"""

from __future__ import annotations

from agent.state import Lead, ScoreBreakdown, Classification


def check_fairness(
    lead_a: Lead,
    lead_b: Lead,
    score_a: ScoreBreakdown,
    score_b: ScoreBreakdown,
    classification_a: Classification,
    classification_b: Classification,
) -> tuple[bool, str]:
    """Check that scoring and classification are identity-blind.

    Two leads differing only in name and email should produce identical
    scores and classifications.

    Args:
        lead_a: First lead.
        lead_b: Second lead (should differ only in name/email from lead_a).
        score_a: Score for lead_a.
        score_b: Score for lead_b.
        classification_a: Classification for lead_a.
        classification_b: Classification for lead_b.

    Returns:
        Tuple of (passed: bool, message: str).
    """
    # Verify firmographic data is identical
    if lead_a.company != lead_b.company:
        return False, "Leads have different company data - fairness check not applicable"

    if lead_a.role != lead_b.role:
        return False, "Leads have different role data - fairness check not applicable"

    if lead_a.message != lead_b.message:
        return False, "Leads have different message data - fairness check not applicable"

    issues: list[str] = []

    # Check score components
    if score_a.industry_match != score_b.industry_match:
        issues.append(f"industry_match differs: {score_a.industry_match} vs {score_b.industry_match}")
    if score_a.company_size != score_b.company_size:
        issues.append(f"company_size differs: {score_a.company_size} vs {score_b.company_size}")
    if score_a.role_match != score_b.role_match:
        issues.append(f"role_match differs: {score_a.role_match} vs {score_b.role_match}")
    if score_a.buying_signal != score_b.buying_signal:
        issues.append(f"buying_signal differs: {score_a.buying_signal} vs {score_b.buying_signal}")
    if score_a.total != score_b.total:
        issues.append(f"total differs: {score_a.total} vs {score_b.total}")

    # Check classification
    if classification_a.label != classification_b.label:
        issues.append(f"classification differs: {classification_a.label} vs {classification_b.label}")

    if issues:
        return False, "Fairness check failed: " + "; ".join(issues)

    return True, "Fairness check passed: score and classification are identity-blind"