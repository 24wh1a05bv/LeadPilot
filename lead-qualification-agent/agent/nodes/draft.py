"""Draft node - creates a personalised outreach email for HOT leads."""

from __future__ import annotations

from datetime import datetime

from agent.state import AgentState, EmailDraft
from agent.llm import LLM


def _generate_email(enrichment, lead, llm: LLM) -> EmailDraft:
    """Generate a personalised outreach email using the LLM.

    Args:
        enrichment: Enriched company data.
        lead: The lead data.
        llm: LLM instance for email generation.

    Returns:
        EmailDraft with grounded_on references.
    """
    enrichment_facts = []
    if enrichment.industry:
        enrichment_facts.append(f"industry: {enrichment.industry}")
    if enrichment.employee_count:
        enrichment_facts.append(f"company size: {enrichment.employee_count} employees")
    if enrichment.revenue_estimate:
        enrichment_facts.append(f"revenue: {enrichment.revenue_estimate}")
    if enrichment.tech_stack:
        enrichment_facts.append(f"tech stack: {', '.join(enrichment.tech_stack[:3])}")
    if enrichment.buying_signal:
        enrichment_facts.append(f"buying signal: {enrichment.buying_signal}")

    system_prompt = (
        "You are a sales outreach email writer. Draft a concise, personalised "
        "first-touch email based on the lead and company data provided. "
        "The email should reference specific company facts from the enrichment data. "
        "Keep it to 3-4 sentences. Include a clear call to action."
    )

    prompt = (
        f"Lead name: {lead.name}\n"
        f"Lead role: {lead.role or 'Unknown'}\n"
        f"Lead company: {lead.company}\n"
        f"Lead message: {lead.message}\n\n"
        f"Enrichment data:\n" + "\n".join(f"- {fact}" for fact in enrichment_facts) + "\n\n"
        "Draft a personalised outreach email."
    )

    try:
        body = llm.generate(system=system_prompt, prompt=prompt, max_tokens=500)
    except Exception:
        body = _fallback_email(lead, enrichment)

    subject = f"Quick question about {lead.company}"

    return EmailDraft(
        subject=subject,
        body=body,
        grounded_on=enrichment_facts,
    )


def _fallback_email(lead, enrichment) -> str:
    """Generate a fallback email when LLM is unavailable."""
    industry_ref = f" in the {enrichment.industry} industry" if enrichment and enrichment.industry else ""

    return (
        f"Hi {lead.name},\n\n"
        f"I hope this message finds you well. I've been following {lead.company}{industry_ref} "
        f"and was impressed by your recent work.\n\n"
        f"We specialize in helping companies streamline their sales operations and drive revenue growth. "
        f"I'd love to explore how we might be able to support {lead.company}'s goals.\n\n"
        f"Would you be open to a brief chat next week?\n\n"
        f"Best regards,\nYour Sales Team"
    )


def draft_node(state: AgentState) -> dict:
    """Draft a personalised outreach email for a HOT lead.

    Only called for HOT leads (enforced by route_decision).

    Args:
        state: Current agent state with enrichment and lead data.

    Returns:
        Dict with updated draft and audit trail entry.
    """
    lead = state.lead
    enrichment = state.enrichment

    # Ensure enrichment exists (should always for HOT leads)
    if enrichment is None:
        from agent.state import Enrichment
        enrichment = Enrichment(source="none")

    # Generate the email
    llm = LLM(temperature=0.3)
    draft = _generate_email(enrichment, lead, llm)

    audit_entry = {
        "node": "draft",
        "timestamp": datetime.now().isoformat(),
        "input": {
            "lead_name": lead.name,
            "lead_company": lead.company,
            "enrichment_source": enrichment.source,
        },
        "output": {
            "subject": draft.subject,
            "grounded_on": draft.grounded_on,
        },
    }

    return {
        "draft": draft,
        "audit_trail": [audit_entry],
    }