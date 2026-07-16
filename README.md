# LeadPilot — AI Lead Qualification & Outreach Agent

> An autonomous AI agent that enriches, scores, classifies, and drafts personalized outreach for B2B inbound leads — with a human-in-the-loop approval gate before anything sends.

**Live Demo:** [leadpilot.onrender.com](https://leadpilot.onrender.com)

---

## Problem Statement

B2B sales teams receive more inbound leads than they can manually work. Reps waste hours on poor-fit leads and are slow to respond to hot ones. Studies show that responding to a lead within 5 minutes increases conversion by **9x** — yet most teams take hours or days.

**LeadPilot** solves this by automating the triage pipeline while keeping a human rep in control of all outbound communication.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                     LeadPilot Pipeline                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Lead Form Submission                                           │
│        │                                                        │
│        ▼                                                        │
│  ┌─────────┐    DuckDuckGo + LLM                               │
│  │ ENRICH  │───→ Company data: industry, size, tech stack,     │
│  │         │    buying signals, source reliability              │
│  └────┬────┘                                                    │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────┐    ICP Config (JSON)                               │
│  │  SCORE  │───→ Industry match +30, Company size +25,         │
│  │         │    Role match +25, Buying signal +20               │
│  └────┬────┘    Total: 0-100                                    │
│       │                                                         │
│       ▼                                                         │
│  ┌──────────┐                                                   │
│  │ CLASSIFY │───→ HOT (≥80) / NURTURE (≥50) / DISQUALIFY (<50) │
│  └────┬─────┘    + cited reason with specific score factors     │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────┐                                                    │
│  │  ROUTE  │───→ HOT: draft email                              │
│  │         │    NURTURE: enroll in sequence                     │
│  │         │    DISQUALIFY: archive                             │
│  │         │    MANUAL_REVIEW: flag for human                   │
│  └────┬────┘                                                    │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────┐                                                    │
│  │  DRAFT  │───→ Personalized email grounded in enrichment data │
│  └────┬────┘    (HOT leads only)                                │
│       │                                                         │
│       ▼                                                         │
│  ╔═══════════╗                                                  │
│  ║ HUMAN GATE║───→ Rep must Approve / Edit / Reject             │
│  ╚═══════╤═══╝    No email sends without approval               │
│          │                                                      │
│          ▼                                                      │
│    Email Sent (or archived)                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### 1. Dual Enrichment Strategy
- **Mock Database** — Instant lookup for known companies (high confidence)
- **DuckDuckGo Web Search** — Fallback for unknown companies using web search + LLM extraction
- **Source Reliability Mapping** — Each data point tagged with reliability (HIGH/MEDIUM/LOW)
- **Field-Level Evidence** — Every extracted field includes the exact quote supporting it
- **Ambiguity Detection** — Warns when company name matches multiple entities

### 2. Intelligent Scoring Engine
- **Case-Insensitive Matching** — "technology" matches "Technology" automatically
- **Role Tokenization** — Fuzzy matching for title variations (VP Sales = Chief Revenue Officer = Sales Director)
- **Keyword-Based Buying Signal** — Instant classification without LLM dependency
- **Configurable ICP** — Edit `icp_config.json` to change scoring rules without code changes

### 3. Role Matching Hierarchy
| Tier | Roles | Score |
|------|-------|-------|
| Executive | CTO, CEO, VP Engineering, VP Sales, Director of Engineering, Head of Sales | 25/25 |
| Senior Manager | Engineering Manager, Sales Manager | 15/25 |
| Manager | Product Manager | 10/25 |
| General | Manager | 5/25 |
| Entry | Intern | 0/25 |

### 4. Buying Signal Classification
| Level | Keywords | Score |
|-------|----------|-------|
| **Strong** | purchase, demo, evaluating vendors, pricing, contract | 20/20 |
| **Medium** | need to, automate, exploring, planning, interested | 12/20 |
| **Weak** | browsing, learning, just checking | 5/20 |
| **None** | No signal detected | 0/20 |

### 5. Confidence Calculation
Confidence is calculated from multiple factors:
- **Source reliability** (Mock DB = HIGH, Wikipedia = MEDIUM, General search = LOW)
- **Unknown factors** (missing industry, company size, etc.)
- **Data completeness** — more verified data = higher confidence

| Confidence | Threshold | Label |
|------------|-----------|-------|
| 90-100% | High | Fully verified data |
| 70-89% | Medium | Most data verified |
| 40-69% | Low | Partial data |
| <40% | Very Low | Minimal data |

---

## Guardrails & Safety

### Prompt Injection Defense
- Message field is **never** concatenated into system prompts
- Lightweight pattern detection catches imperative phrases ("ignore instructions", "mark me HOT")
- Architecture is the real defense: no path from raw text → email send without human approval
- Flagged attempts are logged for security review

### Identity-Blind Scoring (Fairness)
- `lead.name` is **structurally excluded** from the scoring pipeline
- Score depends only on: industry, company size, role, buying signal
- Verified by automated tests: name-swapped leads produce identical scores

### Human Approval Gate
- **No email sends without explicit rep approval**
- Three options: Approve / Edit / Reject
- Approval is logged with timestamp and rep identity
- Email send tool is technically incapable of firing before approval

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Orchestration** | LangGraph / Simple Pipeline | State machine with conditional routing |
| **LLM** | Configurable (Claude/OpenAI/Mock) | Buying signal analysis, email drafting |
| **Structured Output** | Pydantic | Type-safe state, scores, classifications |
| **UI** | Streamlit | Rep-facing dashboard and review screen |
| **Storage** | SQLite | Audit log, CRM writes |
| **Enrichment** | DuckDuckGo + Mock DB | Company data lookup |
| **Testing** | pytest | 19 automated tests across 5 evaluation layers |
| **Deployment** | Render (Docker) | Free tier hosting |

---

## Project Structure

```
LeadPilot/
├── lead-qualification-agent/
│   ├── agent/
│   │   ├── graph.py              # Pipeline orchestration
│   │   ├── state.py              # Pydantic state schema
│   │   ├── llm.py                # LLM wrapper (swappable)
│   │   ├── timestamps.py         # IST timestamp utility
│   │   └── nodes/
│   │       ├── enrich.py         # Company enrichment
│   │       ├── score.py          # ICP scoring engine
│   │       ├── classify.py       # HOT/NURTURE/DISQUALIFY
│   │       ├── route.py          # Routing logic
│   │       └── draft.py          # Email drafting
│   ├── tools/
│   │   ├── enrichment_lookup.py  # Mock DB lookup
│   │   ├── web_search_enrich.py  # DuckDuckGo enrichment
│   │   ├── crm_write.py         # Gated CRM writes
│   │   └── email_send.py        # Gated email sending
│   ├── guardrails/
│   │   ├── prompt_injection.py   # Injection detection
│   │   └── fairness_check.py     # Identity-blind verification
│   ├── data/
│   │   ├── mock_companies.json   # Test company database
│   │   └── icp_config.json       # ICP criteria & scoring
│   ├── ui/
│   │   └── app.py                # Streamlit dashboard
│   ├── tests/
│   │   ├── test_scoring.py       # Score & classification tests
│   │   ├── test_gate.py          # Approval gate tests
│   │   ├── test_fairness.py      # Fairness tests
│   │   └── test_injection.py     # Injection defense tests
│   ├── logs/
│   │   └── audit_log.db          # SQLite audit trail
│   └── requirements.txt
├── Dockerfile                    # Render deployment
├── render.yaml                   # Render blueprint
├── README.md
├── specification.md              # Technical specification
└── Requirements.md               # Business requirements
```

---

## UI Features

### Dashboard
- Total leads, HOT/NURTURE/DISQUALIFY counts, average score
- Classification distribution chart
- Score distribution chart
- Industry breakdown
- Confidence levels

### Inbox
- Filterable, sortable lead table
- CSV bulk import (20+ leads at once)
- Single lead entry form
- Status badges (HOT/NURTURE/DISQUALIFY)

### Lead Detail
- Lead information card
- Company enrichment with source reliability badge
- Expandable field evidence (value, evidence quote, confidence)
- ICP comparison (pass/fail per criteria)
- Score breakdown with points
- Classification with cited reasoning
- Draft email with "Grounded On" facts
- Approval controls (Approve/Edit/Reject)
- Audit timeline

### Audit Log
- Searchable history of all decisions
- Filterable by name, company, or action
- Full reasoning for every classification

---

## Test Results

```
19 tests passed, 0 failed

✓ test_name_swap_fairness          — Name-swap produces identical scores
✓ test_different_firmographics     — Different data → different scores
✓ test_email_send_blocked          — No send without approval
✓ test_email_send_allowed          — Send works after approval
✓ test_email_send_logs_to_audit    — Approval logged correctly
✓ test_injection_flagged           — Injection detected & flagged
✓ test_injection_scoring_intact    — Scoring unaffected by injection
✓ test_injection_no_email_send     — Injection doesn't bypass gate
✓ test_injection_pattern_detection — Pattern matching works
✓ test_non_injection_passes        — Normal messages not flagged
✓ test_hot_lead_classification     — HOT leads classified correctly
✓ test_hot_lead_draft_created      — Email drafted for HOT
✓ test_hot_lead_email_not_sent     — Draft not auto-sent
✓ test_disqualify_low_score        — Low scores → DISQUALIFY
✓ test_disqualify_no_outreach      — No outreach for DISQUALIFY
✓ test_disqualify_unknown_company  — Unknown companies handled
```

### Smoke Test Results
```
TEST 1: HOT lead (Acme Corp, CTO)      → 92/100 HOT  ✓
TEST 2: NURTURE lead (Initech, Dev)     → 55/100 NURTURE  ✓
TEST 3: DISQUALIFY lead (Globex, Ops)   → 32/100 DISQUALIFY  ✓
TEST 4: Injection attempt               → Flagged, buying signal neutralized  ✓
TEST 5: Unknown company                 → Web search fallback works  ✓
```

---

## Evaluation Layers

| Layer | What it tests | How |
|-------|--------------|-----|
| **Trace** | Correct node execution order | Audit trail verification |
| **Tool-Call** | Tools called with correct args | Mock verification |
| **Output** | Score, classification, draft correctness | Assertion on final state |
| **Governance** | Email only sends after approval | Gate enforcement tests |
| **Fairness** | Name-swap produces identical results | Automated name-swap tests |

---

## Deployment

### Render (Free Tier)
1. Push to GitHub
2. Go to [render.com](https://render.com) → New Blueprint
3. Connect repo → Auto-detects `render.yaml`
4. Deploy → Live in ~5 minutes

### Local Development
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run ui/app.py
```

### Run Tests
```bash
pytest tests/ -v
```

---

## Configuration

### ICP Config (`data/icp_config.json`)
```json
{
  "icp_criteria": {
    "target_industries": ["Software", "Technology", "Science"],
    "min_employee_count": 50,
    "max_employee_count": 5000,
    "target_roles": ["CTO", "VP Engineering", "Director of Engineering", "Head of Sales", "CEO"]
  },
  "thresholds": {
    "hot_min": 80,
    "nurture_min": 50
  }
}
```

Modify this file to change:
- Target industries and their scores
- Company size brackets and scores
- Role hierarchy and scores
- Buying signal weights
- Classification thresholds

---

## Architecture Decisions

### Why LangGraph?
- Fixed pipeline (not multi-agent negotiation) — leads need deterministic processing
- `interrupt()` provides native human-approval gate
- State checkpointing enables resume after approval

### Why Pydantic?
- Typed state schema prevents runtime errors
- Structured output enables deterministic fairness testing
- Score, classification, and draft are typed objects, never free text

### Why Keyword + LLM for Buying Signal?
- Keywords provide instant, deterministic classification for common phrases
- LLM fallback handles edge cases and nuanced messages
- No external API dependency for basic operation

### Why Mock DB + Web Search?
- Mock DB: Instant, free, high confidence for known companies
- Web Search: Handles any company, but slower and lower confidence
- Dual strategy balances speed with coverage

---

## Future Improvements

- [ ] **Meeting Booking** — Auto-schedule meetings for HOT leads after approval
- [ ] **Follow-up Cadence** — Automated nurture sequences with timed re-evaluation
- [ ] **Multi-Model Scoring** — Second-model re-score to catch bias
- [ ] **CRM Integration** — Real Salesforce/HubSpot integration
- [ ] **Email Provider** — Real email sending via SendGrid/SES
- [ ] **Multi-Tenant** — Support multiple ICPs per organization
- [ ] **Analytics Dashboard** — Conversion tracking, rep performance metrics
- [ ] **A/B Testing** — Test different email templates and scoring rules

---

## License

This project was built as an academic demonstration of AI agent architecture with human-in-the-loop safety patterns.

---

**Built with:** Python, LangGraph, Streamlit, Pydantic, DuckDuckGo, SQLite
