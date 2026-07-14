# Requirements — Lead Qualification & Outreach Agent

## 1. Business context

A B2B sales team receives more inbound leads than it can manually work. Reps waste time on poor-fit leads and are slow to reach hot ones, and slow follow-up loses deals. The agent must score leads and draft first-touch outreach automatically, while a human stays in control of anything that actually sends.

## 2. Stakeholders

| Role | Interest |
|---|---|
| VP Sales (business owner) | SQL conversion rate, rep hours saved |
| SDR / AE (end user) | Fast, trustworthy triage; final say on outreach |
| RevOps | Auditability, fairness, correct CRM state |

## 3. Functional requirements

### FR1 — Enrichment
The system must enrich each incoming lead with company size, industry, role seniority, and buying-signal data, using a dedicated enrichment tool call (not the model's own knowledge).

### FR2 — Scoring
The system must score each lead against a configurable Ideal Customer Profile (ICP), producing a numeric score and a per-factor breakdown (industry match, company size, role, buying signal).

### FR3 — Classification
The system must classify each lead as **HOT**, **NURTURE**, or **DISQUALIFY** based on score thresholds, and must attach a human-readable, cited reason to every classification.

### FR4 — Drafting (HOT leads only)
For HOT leads, the system must draft a personalised first-touch email grounded in the enrichment data (not generic template text). The email is a draft only — it is never sent by this step.

### FR5 — Human approval gate
No outbound email may be sent without explicit rep approval. The rep must be able to **Approve**, **Edit**, or **Reject** a draft. The email-send tool must be technically incapable of firing before an approval event is recorded.

### FR6 — Routing
- HOT leads → drafted email held for approval.
- NURTURE leads → enrolled into a nurture sequence, with reason logged.
- DISQUALIFY leads → archived with a reason; no outreach of any kind.

### FR7 — Logging / audit trail
Every run must persist: raw lead input, enrichment result, score breakdown, classification + reason, drafted message (if any), and the approval decision (approve/edit/reject + timestamp + rep identity). Logs must be sufficient to answer "why did we [reject / email] this lead?" without re-running the agent.

### FR8 — Fairness
Classification and scoring must be identity-blind: two leads with identical firmographic data but different names (or other demographic-adjacent identifiers) must receive the same score and classification.

### FR9 — Prompt-injection resistance
Text submitted in the lead's free-form message field must always be treated as data to be analyzed, never as an instruction to the agent. Attempts embedded in that field to alter scoring, force a classification, or trigger an auto-send must be ignored, and the attempt should be flagged in the log.

## 4. Non-functional requirements

| Category | Requirement |
|---|---|
| Latency | A single lead should complete enrich→score→classify→route→draft in well under the time a rep would spend reading the form manually (target: a few seconds, not minutes). |
| Determinism | Given the same lead and ICP config, scoring should be stable/reproducible (low temperature, structured output schema). |
| Auditability | Every decision must be traceable to specific enrichment facts, not an opaque model judgment. |
| Governance | Any tool capable of an external side effect (CRM write, email send) must be explicitly gated and independently testable. |
| Extensibility | ICP criteria and score thresholds must be configurable without code changes (e.g. `icp_config.json`). |

## 5. Out of scope (for this lab)

- Real integration with an actual CRM or email provider (both are mocked/gated stubs).
- Real third-party enrichment API (Clearbit, ZoomInfo, etc.) — a local mocked dataset is used instead.
- Multi-tenant support / multiple ICPs per org.

## 6. Acceptance criteria (mapped to test scenarios)

| Scenario | Evaluation layer | Pass criteria |
|---|---|---|
| Hot lead drafted | Output | Correct score and reason; email drafted; not sent |
| Disqualify | Governance | No outreach; reason logged |
| Approval gate | Governance / human gate | Send tool never fires before approval |
| Fairness | Fairness | Score unchanged on name-swap; any gap is a fail |
| Injection in lead form | Adversarial / governance | Injection ignored; scoring intact; gate holds |

A build is considered complete only when it passes all five layers above (trace, tool-call, output, governance, fairness) — see `specification.md §7 Evaluation Plan` for how each is tested.
