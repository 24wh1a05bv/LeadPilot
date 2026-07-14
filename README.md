# Lead Qualification & Outreach Agent

An autonomous agent that enriches, scores, and classifies inbound B2B leads, drafts a personalised first-touch email for the best ones, and routes everything else — all with a human rep in control of anything that leaves the building.

**Business owner:** VP Sales · **Function:** Sales / RevOps
**User:** SDR / Account Executive
**KPI:** SQL conversion rate, speed-to-lead, rep hours saved

---

## What it does

```
Lead form submission
        │
        ▼
   [ enrich ]  → look up company, size, industry, buying signals
        │
        ▼
   [ score ]   → compare against Ideal Customer Profile (ICP)
        │
        ▼
 [ classify ]  → HOT / NURTURE / DISQUALIFY, with a cited reason
        │
        ▼
   [ route ]   → nurture sequence / archive / continue to draft
        │
        ▼
   [ draft ]   → personalised outreach email (HOT leads only)
        │
        ▼
 ── HUMAN GATE ──  rep must Approve / Edit / Reject
        │
        ▼
  email-send tool (only fires after approval)
```

Every step is logged: enrichment source, score breakdown, classification reason, and the drafted message — so any decision can be explained after the fact.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Orchestration | **LangGraph** | Pipeline is a fixed state machine, not a negotiating multi-agent crew. `interrupt()` gives a native, resumable human-approval gate. |
| LLM | Configurable (Claude / OpenAI-compatible) via a single `llm.py` wrapper | Swappable without touching graph logic; also enables the stretch goal of a second-model re-score. |
| Structured output | **Pydantic** | Score, classification, and email draft are typed objects, never free text — required for deterministic fairness testing. |
| UI | **Streamlit** | Fast to build the rep-facing review screen: lead card, score breakdown, Approve/Edit/Reject buttons. |
| Storage | **SQLite** (or JSON, for zero-setup) | Backs the mocked CRM-write tool and the audit log. |
| Enrichment tool | Local mocked company lookup (JSON) | Deterministic, no external API dependency, easy to craft test fixtures for (e.g. name-swap fairness pairs). |
| Testing | **pytest** + custom eval harness | Covers the five required evaluation layers: trace, tool-call, output, governance, fairness. |

---

## Project structure

```
lead-qualification-agent/
├── README.md
├── Requirements.md
├── specification.md
├── agent/
│   ├── graph.py            # LangGraph StateGraph definition
│   ├── state.py             # Shared state schema (Pydantic)
│   ├── nodes/
│   │   ├── enrich.py
│   │   ├── score.py
│   │   ├── classify.py
│   │   ├── route.py
│   │   └── draft.py
│   └── llm.py                # Model wrapper
├── tools/
│   ├── enrichment_lookup.py
│   ├── crm_write.py           # gated
│   └── email_send.py          # gated
├── guardrails/
│   ├── prompt_injection.py
│   └── fairness_check.py
├── data/
│   ├── mock_companies.json
│   └── icp_config.json
├── ui/
│   └── app.py                 # Streamlit app
├── logs/
│   └── audit_log.db
├── tests/
│   ├── test_scoring.py
│   ├── test_gate.py
│   ├── test_fairness.py
│   └── test_injection.py
└── requirements.txt
```

---

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# set your model provider key
export ANTHROPIC_API_KEY=...   # or OPENAI_API_KEY

streamlit run ui/app.py
```

## Running tests

```bash
pytest tests/ -v
```

---

## Status

Scaffolding stage — see `Requirements.md` for business/functional requirements and `specification.md` for the technical design (state schema, node contracts, tool gating, evaluation plan).

## Stretch goals

- Meeting-booking tool for approved HOT leads
- Automated follow-up cadence for NURTURE leads
- Second-model re-score to catch first model's bias
