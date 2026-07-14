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
    source: str = ""  # which mocked lookup matched


class ScoreBreakdown(BaseModel):
    """Per-factor score breakdown."""
    industry_match: int = 0
    company_size: int = 0
    role_match: int = 0
    buying_signal: int = 0
    total: int = 0


class Classification(BaseModel):
    """Lead classification result."""
    label: Literal["HOT", "NURTURE", "DISQUALIFY"]
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