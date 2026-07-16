"""Shared state schema for the Lead Qualification Agent."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Lead(BaseModel):
    """Incoming lead from a web form."""
    name: str
    email: str
    company: str
    role: str | None = None
    message: str = ""  # raw free-text, always treated as data


class Enrichment(BaseModel):
    """Enriched company data from lookup tool."""
    industry: str | None = None
    employee_count: int | None = None
    revenue_estimate: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    buying_signal: str | None = None
    source: str = ""  # which lookup matched (mock DB or web search)
    source_reliability: str = "high"  # "high", "medium", "low" - reliability of the source
    confidence: str = "high"  # "high", "medium", "low" - confidence in extracted data
    unknown_factors: list[str] = Field(default_factory=list)  # fields that couldn't be determined
    field_evidence: dict[str, dict] = Field(default_factory=dict)  # per-field evidence from web search
    ambiguity_warning: str | None = None  # warning for ambiguous company name matches


class ScoreBreakdown(BaseModel):
    """Per-factor score breakdown."""
    industry_match: int = 0
    company_size: int = 0
    role_match: int = 0
    buying_signal: int = 0
    total: int = 0
    buying_signal_level: str | None = None
    industry_actual: str | None = None
    employee_count_actual: int | None = None
    role_actual: str | None = None
    confidence: str = "high"  # overall confidence in the score
    unknown_factors: list[str] = Field(default_factory=list)


class Classification(BaseModel):
    """Lead classification result."""
    label: Literal["HOT", "NURTURE", "DISQUALIFY", "MANUAL_REVIEW"]
    reason: str  # cited, references specific score factors


class EmailDraft(BaseModel):
    """Drafted outreach email for HOT leads."""
    subject: str
    body: str
    grounded_on: list[str] = Field(default_factory=list)  # enrichment facts referenced


class ApprovalDecision(BaseModel):
    """Human rep's decision on a draft."""
    action: Literal["approve", "edit", "reject"]
    edited_body: str | None = None
    rep_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)


class AgentState(BaseModel):
    """Full state of the lead qualification graph."""
    lead: Lead
    enrichment: Enrichment | None = None
    score: ScoreBreakdown | None = None
    classification: Classification | None = None
    draft: EmailDraft | None = None
    approval: ApprovalDecision | None = None
    injection_flagged: bool = False
    audit_trail: list[dict] = Field(default_factory=list)