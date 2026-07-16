"""Streamlit UI for the Lead Qualification Agent.

Four views:
1. Dashboard - analytics charts and lead distribution
2. Inbox - table of leads with CSV import and single form
3. Lead detail - full details with ICP comparison, reasoning, approval gate
4. Audit log - searchable timeline history
"""

from __future__ import annotations

import csv
import io
import json
import sys
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import streamlit as st

IST = timezone(timedelta(hours=5, minutes=30))


def _format_ist(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        dt = dt.astimezone(IST)
        return dt.strftime("%I:%M:%S %p IST")
    except Exception:
        return ts[:19]

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.state import Lead, AgentState, ApprovalDecision, EmailDraft
from agent.graph import create_graph, run_agent
from tools.crm_write import read_audit_log


# ---- Helpers ----

def _load_icp_config() -> dict:
    config_path = Path(__file__).parent.parent / "data" / "icp_config.json"
    with open(config_path) as f:
        return json.load(f)


def _safe(value, fallback="Unknown"):
    return fallback if value is None else value


def _confidence_pct(result: dict) -> int:
    score = result.get("score")
    enrichment = result.get("enrichment", {})
    if not score:
        return 0
    factors_present = 0
    total_factors = 4
    if enrichment.get("industry"):
        factors_present += 1
    if enrichment.get("employee_count"):
        factors_present += 1
    if enrichment.get("source") and enrichment.get("source") != "no match found":
        factors_present += 1
    if score.get("buying_signal", 0) > 0:
        factors_present += 1
    return int((factors_present / total_factors) * 100)


def _confidence_label(pct: int) -> str:
    if pct >= 90:
        return "High"
    elif pct >= 70:
        return "Medium"
    elif pct >= 40:
        return "Low"
    return "Very Low"


def _icp_status(actual, expected_list=None, expected_range=None) -> tuple[str, str]:
    if actual is None:
        return "fail", "Unknown"
    if expected_list:
        if actual in expected_list:
            return "pass", "Match"
        return "fail", "No match"
    if expected_range:
        lo, hi = expected_range
        if isinstance(actual, (int, float)) and lo <= actual <= hi:
            return "pass", "Within range"
        if isinstance(actual, (int, float)):
            return "fail", f"Outside range ({lo}-{hi})"
    return "warn", "Partial"


def _score_icon(score_val: int, max_val: int) -> str:
    ratio = score_val / max_val if max_val else 0
    if ratio >= 0.7:
        return "strong"
    elif ratio > 0:
        return "weak"
    return "none"


# ---- Session state initialization ----

def init_session_state() -> None:
    if "leads" not in st.session_state:
        st.session_state.leads = []
    if "results" not in st.session_state:
        st.session_state.results = {}
    if "current_index" not in st.session_state:
        st.session_state.current_index = None


# ---- Lead processing ----

def process_lead(lead_dict: dict) -> dict:
    app = create_graph()
    lead = Lead(**lead_dict)
    input_state = {"lead": lead}
    result = app.invoke(input_state)
    return result


# ---- CSV import ----

def render_csv_import() -> None:
    with st.expander("Bulk Import from CSV", expanded=False):
        st.write("Upload a CSV file with columns: `name`, `email`, `company` (required), `role`, `message` (optional).")

        uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"], key="csv_upload")

        if uploaded_file is not None:
            try:
                content = uploaded_file.read().decode("utf-8")
                reader = csv.DictReader(io.StringIO(content))
                rows = list(reader)

                if not rows:
                    st.error("CSV file is empty.")
                    return

                required_cols = {"name", "email", "company"}
                actual_cols = set(reader.fieldnames or [])
                missing = required_cols - actual_cols
                if missing:
                    st.error(f"Missing required columns: {', '.join(missing)}")
                    return

                st.write(f"Found **{len(rows)}** leads. Preview:")
                st.dataframe(rows[:5], width="stretch")
                if len(rows) > 5:
                    st.caption(f"Showing first 5 of {len(rows)} rows")

                if st.button("Import & Process All Leads", type="primary", width="stretch"):
                    progress = st.progress(0, text="Processing leads...")
                    imported = 0
                    errors = 0

                    for i, row in enumerate(rows):
                        name = (row.get("name") or "").strip()
                        email = (row.get("email") or "").strip()
                        company = (row.get("company") or "").strip()

                        if not name or not email or not company:
                            errors += 1
                            continue

                        # Skip duplicates
                        if email in st.session_state.results:
                            continue

                        lead_data = {
                            "name": name,
                            "email": email,
                            "company": company,
                            "role": (row.get("role") or "").strip() or None,
                            "message": (row.get("message") or "").strip(),
                        }

                        try:
                            result = process_lead(lead_data)
                            st.session_state.leads.append(lead_data)
                            st.session_state.results[email] = result
                            imported += 1
                        except Exception as e:
                            errors += 1
                            import traceback
                            st.error(f"Error processing {email}: {e}")
                            st.code(traceback.format_exc())

                        progress.progress(
                            (i + 1) / len(rows),
                            text=f"Processing {i + 1}/{len(rows)}...",
                        )

                    progress.empty()
                    st.success(f"Imported **{imported}** leads. Errors: {errors}")
                    if imported > 0:
                        st.session_state.current_index = len(st.session_state.leads) - imported
                        st.rerun()

            except Exception as e:
                st.error(f"Error reading CSV: {e}")


# ---- Lead form ----

def render_lead_form() -> None:
    with st.expander("Add New Lead", expanded=False):
        with st.form("lead_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Name*", placeholder="e.g. John Smith")
                company = st.text_input("Company*", placeholder="e.g. Acme Corp")
                role = st.text_input("Role", placeholder="e.g. CTO")
            with col2:
                email = st.text_input("Email*", placeholder="e.g. john@acme.com")
                message = st.text_area("Message", placeholder="How did they hear about you? What are they interested in?", height=100)

            submitted = st.form_submit_button("Submit Lead", type="primary", width="stretch")

            if submitted:
                if not name or not email or not company:
                    st.error("Name, Email, and Company are required.")
                else:
                    lead_data = {
                        "name": name,
                        "email": email,
                        "company": company,
                        "role": role if role else None,
                        "message": message,
                    }
                    with st.spinner("Processing lead..."):
                        result = process_lead(lead_data)

                    st.session_state.leads.append(lead_data)
                    st.session_state.results[email] = result
                    st.session_state.current_index = len(st.session_state.leads) - 1
                    st.success(f"Lead processed! Classification: {result.get('classification', {}).get('label', 'UNKNOWN')}")
                    st.rerun()


# ---- Inbox view ----

def render_inbox() -> None:
    st.subheader("Inbox")

    render_csv_import()
    render_lead_form()

    if not st.session_state.leads:
        st.info("No leads yet. Add a lead using the form above or import a CSV.")
        return

    # Filter controls
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        search = st.text_input("Search by name or company", placeholder="Type to filter...", key="inbox_search")
    with col2:
        filter_class = st.selectbox("Filter by classification", ["All", "HOT", "NURTURE", "DISQUALIFY", "PENDING"], key="inbox_filter")
    with col3:
        sort_by = st.selectbox("Sort by", ["Score (high)", "Score (low)", "Name"], key="inbox_sort")

    table_data = []
    for i, lead_data in enumerate(st.session_state.leads):
        result = st.session_state.results.get(lead_data["email"], {})
        classification = result.get("classification", {})
        score = result.get("score", {})
        enrichment = result.get("enrichment", {})

        label = classification.get("label", "PENDING")
        total_score = score.get("total", 0) if score else 0
        industry = _safe(enrichment.get("industry")) if enrichment else "Unknown"

        if label == "HOT":
            badge = "HOT"
        elif label == "NURTURE":
            badge = "NURTURE"
        elif label == "DISQUALIFY":
            badge = "DISQUALIFY"
        else:
            badge = "PENDING"

        table_data.append({
            "idx": i,
            "Name": lead_data["name"],
            "Company": lead_data["company"],
            "Industry": industry,
            "Score": total_score,
            "Status": badge,
        })

    # Apply filters
    if search:
        search_lower = search.lower()
        table_data = [r for r in table_data if search_lower in r["Name"].lower() or search_lower in r["Company"].lower()]

    if filter_class != "All":
        table_data = [r for r in table_data if r["Status"] == filter_class]

    # Apply sorting
    if sort_by == "Score (high)":
        table_data.sort(key=lambda x: x["Score"], reverse=True)
    elif sort_by == "Score (low)":
        table_data.sort(key=lambda x: x["Score"])
    elif sort_by == "Name":
        table_data.sort(key=lambda x: x["Name"])

    if not table_data:
        st.info("No leads match the current filters.")
        return

    display_data = [{"#": i + 1, "Name": r["Name"], "Company": r["Company"], "Industry": r["Industry"], "Score": r["Score"], "Status": r["Status"]} for i, r in enumerate(table_data)]

    st.data_editor(
        display_data,
        width="stretch",
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn(width=40),
            "Status": st.column_config.TextColumn(width=130),
        },
        disabled=True,
    )


# ---- Dashboard view ----

def render_dashboard() -> None:
    st.subheader("Dashboard")

    if not st.session_state.leads:
        st.info("No data yet. Process some leads to see analytics.")
        return

    leads = st.session_state.leads
    results = st.session_state.results

    # ---- Summary metrics ----
    classifications = []
    scores = []
    confidences = []
    industries = []
    for lead in leads:
        r = results.get(lead["email"], {})
        cls = r.get("classification", {})
        sc = r.get("score")
        enr = r.get("enrichment", {})
        classifications.append(cls.get("label", "PENDING"))
        if sc:
            scores.append(sc.get("total", 0))
        confidences.append(_confidence_pct(r))
        industries.append(_safe(enr.get("industry")) if enr else "Unknown")

    total = len(leads)
    hot = classifications.count("HOT")
    nurture = classifications.count("NURTURE")
    disqualify = classifications.count("DISQUALIFY")
    pending = classifications.count("PENDING")
    avg_score = sum(scores) / len(scores) if scores else 0
    avg_conf = sum(confidences) / len(confidences) if confidences else 0

    # ---- Top row metrics ----
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Total Leads", total)
    with c2:
        st.metric("HOT", hot, delta=None)
    with c3:
        st.metric("NURTURE", nurture, delta=None)
    with c4:
        st.metric("DISQUALIFY", disqualify, delta=None)
    with c5:
        st.metric("Avg Score", f"{avg_score:.0f}")

    st.divider()

    # ---- Charts row ----
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("### Classification Distribution")
        chart_data = {"HOT": hot, "NURTURE": nurture, "DISQUALIFY": disqualify}
        if pending:
            chart_data["PENDING"] = pending
        st.bar_chart(chart_data, color="#ff4b4b")

    with col_right:
        st.markdown("### Score Distribution")
        if scores:
            score_buckets = {"0-25": 0, "26-50": 0, "51-75": 0, "76-100": 0}
            for s in scores:
                if s <= 25:
                    score_buckets["0-25"] += 1
                elif s <= 50:
                    score_buckets["26-50"] += 1
                elif s <= 75:
                    score_buckets["51-75"] += 1
                else:
                    score_buckets["76-100"] += 1
            st.bar_chart(score_buckets, color="#00c04b")
        else:
            st.info("No scores available")

    st.divider()

    # ---- Second row ----
    col_ind, col_conf = st.columns(2)

    with col_ind:
        st.markdown("### Industry Breakdown")
        industry_counts = Counter(industries)
        if industry_counts:
            st.bar_chart(dict(industry_counts.most_common(10)), color="#1c83e1")

    with col_conf:
        st.markdown("### Confidence Levels")
        conf_labels = [_confidence_label(c) for c in confidences]
        conf_counts = Counter(conf_labels)
        if conf_counts:
            st.bar_chart(dict(conf_counts), color="#ffc107")

    st.divider()

    # ---- Lead list ----
    st.markdown("### All Leads")

    table_data = []
    for i, lead in enumerate(leads):
        r = results.get(lead["email"], {})
        cls = r.get("classification", {})
        sc = r.get("score")
        enr = r.get("enrichment", {})
        table_data.append({
            "Name": lead["name"],
            "Company": lead["company"],
            "Score": sc.get("total", 0) if sc else 0,
            "Classification": cls.get("label", "PENDING"),
            "Industry": _safe(enr.get("industry")) if enr else "Unknown",
            "Confidence": f"{_confidence_pct(r)}%",
        })

    st.dataframe(table_data, width="stretch", hide_index=True)


# ---- Lead detail view ----

def render_lead_detail() -> None:
    st.subheader("Lead Detail")

    if not st.session_state.leads:
        return

    lead_names = [f"{l['name']} - {l['company']}" for l in st.session_state.leads]
    selected_idx = st.selectbox(
        "Select a lead",
        range(len(lead_names)),
        format_func=lambda i: lead_names[i],
        index=st.session_state.current_index if st.session_state.current_index is not None else 0,
    )
    st.session_state.current_index = selected_idx

    lead_data = st.session_state.leads[selected_idx]
    result = st.session_state.results.get(lead_data["email"], {})
    score = result.get("score")
    classification = result.get("classification", {})
    enrichment = result.get("enrichment", {}) or {}
    draft = result.get("draft")
    approval = result.get("approval")
    icp = _load_icp_config()
    icp_criteria = icp["icp_criteria"]

    # ---- 1. Lead Information ----
    st.markdown("---")
    st.markdown("### Lead Information")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Name:** {lead_data['name']}")
        st.write(f"**Email:** {lead_data['email']}")
    with col2:
        st.write(f"**Company:** {lead_data['company']}")
        st.write(f"**Role:** {_safe(lead_data.get('role'))}")
    if lead_data.get("message"):
        st.write(f"**Message:** {lead_data['message']}")

    # ---- 2. Company Enrichment ----
    st.markdown("---")
    st.markdown("### Company Enrichment")

    if enrichment.get("source") and enrichment["source"] != "no match found":
        st.success(f"Data found via: {enrichment['source']}")
        
        # Source reliability badge
        source_rel = enrichment.get("source_reliability", "unknown")
        rel_colors = {"high": "green", "medium": "orange", "low": "red"}
        rel_color = rel_colors.get(source_rel, "gray")
        st.markdown(f"**Source Reliability:** :{rel_color}[{source_rel.upper()}]")
        
        # Main metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Industry", _safe(enrichment.get("industry")))
        with col2:
            emp = enrichment.get("employee_count")
            st.metric("Employees", _safe(emp))
        with col3:
            st.metric("Revenue", _safe(enrichment.get("revenue_estimate")))
        
        if enrichment.get("tech_stack"):
            st.write(f"**Tech Stack:** {', '.join(enrichment['tech_stack'])}")
        if enrichment.get("buying_signal"):
            st.write(f"**Buying Signal:** {enrichment['buying_signal']}")
        
        # Expandable evidence for each field
        field_evidence = enrichment.get("field_evidence", {})
        if field_evidence:
            st.markdown("#### Field Evidence")
            for field_name, evidence_data in field_evidence.items():
                if isinstance(evidence_data, dict):
                    evidence_text = evidence_data.get("evidence", "No evidence available")
                    field_confidence = evidence_data.get("confidence", "unknown")
                    field_value = evidence_data.get("value", "N/A")
                    
                    with st.expander(f"{field_name.replace('_', ' ').title()}: {field_value} ({field_confidence} confidence)"):
                        st.write(f"**Value:** {field_value}")
                        st.write(f"**Evidence:** {evidence_text}")
                        st.write(f"**Confidence:** {field_confidence}")
        
        # Unknown factors
        unknown_factors = enrichment.get("unknown_factors", [])
        if unknown_factors:
            st.warning(f"**Unknown factors:** {', '.join(unknown_factors)}")
        
        # Ambiguity warning
        ambiguity_warning = enrichment.get("ambiguity_warning")
        if ambiguity_warning:
            st.info(f"**Ambiguity detected:** {ambiguity_warning}")
    else:
        st.warning("No company data found")
        st.write("Company not found in enrichment database. Scoring is based on available signals only.")

    # ---- 3. ICP Comparison ----
    st.markdown("---")
    st.markdown("### Ideal Customer Profile Comparison")

    if score:
        icp_industries = icp_criteria["target_industries"]
        actual_industry = score.get("industry_actual")
        ind_status, ind_detail = _icp_status(actual_industry, expected_list=icp_industries)

        actual_emp = score.get("employee_count_actual")
        emp_status, emp_detail = _icp_status(actual_emp, expected_range=(icp_criteria["min_employee_count"], icp_criteria["max_employee_count"]))

        icp_roles = icp_criteria["target_roles"]
        actual_role = score.get("role_actual")
        role_status, role_detail = _icp_status(actual_role, expected_list=icp_roles)

        actual_bs = score.get("buying_signal_level")
        bs_status = "pass" if actual_bs in ("strong", "medium") else ("warn" if actual_bs == "weak" else "fail")
        bs_detail = {"strong": "Strong intent", "medium": "Moderate interest", "weak": "Weak signal", "none": "No signal", None: "Unknown"}.get(actual_bs, "Unknown")

        icp_items = [
            ("Industry", _safe(actual_industry), f"Expected: {', '.join(icp_industries)}", ind_status),
            ("Company Size", _safe(actual_emp), f"Expected: {icp_criteria['min_employee_count']}-{icp_criteria['max_employee_count']} employees", emp_status),
            ("Role", _safe(actual_role), f"Expected: {', '.join(icp_roles)}", role_status),
            ("Buying Signal", bs_detail, "Expected: Strong/Medium intent", bs_status),
        ]

        for label, actual_val, expected_text, status in icp_items:
            with st.container():
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    st.write(f"**{label}**")
                    st.caption(expected_text)
                with c2:
                    st.write(f"**Actual:** {actual_val}")
                with c3:
                    if status == "pass":
                        st.success("Pass")
                    elif status == "warn":
                        st.warning("Partial")
                    else:
                        st.error("Fail")
                st.divider()

    # ---- 4. Score Breakdown ----
    st.markdown("---")
    st.markdown("### Score Breakdown")

    if score:
        def _score_row(label: str, val: int, max_val: int, actual: str = "Unknown"):
            c1, c2, c3 = st.columns([3, 2, 1])
            with c1:
                st.write(f"**{label}**")
            with c2:
                st.write(actual)
            with c3:
                st.write(f"+{val} / {max_val}")

        _score_row("Industry", score.get("industry_match", 0), 30, _safe(score.get("industry_actual")))
        _score_row("Company Size", score.get("company_size", 0), 25, _safe(score.get("employee_count_actual"), "Unknown"))
        _score_row("Role", score.get("role_match", 0), 25, _safe(score.get("role_actual"), "Unknown"))
        _score_row("Buying Signal", score.get("buying_signal", 0), 20, _safe(score.get("buying_signal_level"), "Unknown"))
        st.divider()
        st.metric("Total Score", f"{score.get('total', 0)} / 100")

    # ---- 5. Classification ----
    st.markdown("---")
    st.markdown("### Classification")

    if classification:
        label = classification.get("label", "UNKNOWN")
        if label == "HOT":
            st.error(f"### {label}")
        elif label == "NURTURE":
            st.warning(f"### {label}")
        else:
            st.info(f"### {label}")

    # ---- 6. Reasoning ----
    st.markdown("---")
    st.markdown("### Reasoning")

    if score:
        icp_industries = icp_criteria["target_industries"]
        icp_roles = icp_criteria["target_roles"]

        if score.get("industry_match", 0) >= 20:
            st.write(f"- Strong industry match ({_safe(score.get('industry_actual'))}) +{score['industry_match']}")
        elif score.get("industry_match", 0) > 0:
            st.write(f"- Partial industry match ({_safe(score.get('industry_actual'))}) +{score['industry_match']}")
        else:
            st.write(f"- Company information unavailable or non-target industry")

        if score.get("company_size", 0) >= 20:
            st.write(f"- Company size within target range ({_safe(score.get('employee_count_actual'))} employees) +{score['company_size']}")
        elif score.get("company_size", 0) > 0:
            st.write(f"- Company size partially matches +{score['company_size']}")
        else:
            emp = score.get("employee_count_actual")
            if emp is None:
                st.write(f"- Company size unknown")
            elif emp < icp_criteria["min_employee_count"]:
                st.write(f"- Company too small ({emp} employees, need {icp_criteria['min_employee_count']}+)")
            else:
                st.write(f"- Company too large ({emp} employees)")

        if score.get("role_match", 0) >= 20:
            st.write(f"- Role matches target ({_safe(score.get('role_actual'))}) +{score['role_match']}")
        elif score.get("role_match", 0) > 0:
            st.write(f"- Role partially matches ({_safe(score.get('role_actual'))}) +{score['role_match']}")
        else:
            st.write(f"- Role is outside target profile ({_safe(score.get('role_actual'))})")

        bs_level = score.get("buying_signal_level")
        if bs_level in ("strong", "medium"):
            st.write(f"- Buying intent detected ({bs_level}) +{score['buying_signal']}")
        elif bs_level == "weak":
            st.write(f"- Weak buying signal +{score['buying_signal']}")
        else:
            st.write(f"- No immediate buying intent detected")

    # ---- 7. Action Taken ----
    st.markdown("---")
    st.markdown("### Action Taken")

    if classification:
        label = classification.get("label", "UNKNOWN")
        if label == "HOT":
            st.write("- Archived: Pending human approval")
            st.write("- Logged: Yes")
            if draft:
                st.write("- Email draft: Created")
            else:
                st.write("- Email draft: Not created")
            st.write("- CRM Outreach: Pending approval")
        elif label == "NURTURE":
            st.write("- Archived: No (enrolled in nurture)")
            st.write("- Logged: Yes")
            st.write("- Email draft: Not created (NURTURE lead)")
            st.write("- CRM Outreach: Nurture sequence enrolled")
        else:
            st.write("- Archived: Yes")
            st.write("- Logged: Yes")
            st.write("- Email draft: Not created (DISQUALIFY lead)")
            st.write("- CRM Outreach: None")

    # ---- 8. Fairness Indicator ----
    st.markdown("---")
    st.markdown("### Fairness Check")
    st.write("- Personal identifiers (name, email) excluded from scoring")
    st.write("- Score based only on: industry, company size, role, buying signal")
    if result.get("injection_flagged"):
        st.write("- Injection detected: buying signal neutralized to prevent manipulation")

    # ---- 9. Confidence ----
    st.markdown("---")
    st.markdown("### Confidence")

    conf_pct = _confidence_pct(result)
    conf_label = _confidence_label(conf_pct)

    if conf_pct >= 75:
        st.success(f"**{conf_label}** ({conf_pct}%)")
    elif conf_pct >= 50:
        st.warning(f"**{conf_label}** ({conf_pct}%)")
    else:
        st.error(f"**{conf_label}** ({conf_pct}%)")

    reasons = []
    if not enrichment.get("industry"):
        reasons.append("Company enrichment unavailable")
    if not enrichment.get("employee_count"):
        reasons.append("Company size unknown")
    if enrichment.get("source") == "no match found":
        reasons.append("Company not found in database")
    if not score or not score.get("buying_signal_level"):
        reasons.append("Buying signal indeterminate")
    if reasons:
        st.caption("Factors: " + "; ".join(reasons))
    else:
        st.caption("All scoring factors available")

    # ---- 10. Injection Warning ----
    if result.get("injection_flagged"):
        st.markdown("---")
        st.error(
            "Injection Flagged - The lead's message contained patterns "
            "that suggest a prompt injection attempt. The buying signal was "
            "scored as neutral. This lead should be manually reviewed."
        )

    # ---- 11. Email Draft & Approval (Human Gate) ----
    if draft:
        st.markdown("---")
        st.markdown("### Draft Email")

        st.write(f"**Subject:** {draft.get('subject', 'N/A')}")
        email_body = draft.get("body", "")

        st.markdown("---")
        st.text_area("Review", email_body, height=250, key=f"email_body_{selected_idx}", disabled=True)
        st.markdown("---")

        grounded_on = draft.get("grounded_on", [])
        if grounded_on:
            with st.expander("Grounded On (enrichment facts used)"):
                for fact in grounded_on:
                    st.write(f"- {fact}")

        st.markdown("### Approval Required")
        st.caption("No email will be sent until you approve.")

        col_a, col_b, col_c = st.columns([1, 1, 1])

        with col_a:
            if st.button("Approve", key=f"approve_{selected_idx}", type="primary", width="stretch"):
                _handle_approval(lead_data, result, "approve", selected_idx)
                st.rerun()

        with col_b:
            edited_body = st.text_area(
                "Edit body before approving:",
                draft.get("body", ""),
                height=100,
                key=f"edit_body_{selected_idx}",
                label_visibility="collapsed",
            )
            if st.button("Approve with Edit", key=f"edit_{selected_idx}", width="stretch"):
                _handle_approval(lead_data, result, "edit", selected_idx, edited_body)
                st.rerun()

        with col_c:
            if st.button("Reject", key=f"reject_{selected_idx}", width="stretch"):
                _handle_approval(lead_data, result, "reject", selected_idx)
                st.rerun()

    elif classification and classification.get("label") == "HOT":
        st.info("Draft not yet generated. The lead may still be processing.")

    # ---- 12. Audit Timeline ----
    st.markdown("---")
    st.markdown("### Audit Timeline")

    audit_trail = result.get("audit_trail", [])
    if audit_trail:
        for entry in audit_trail:
            ts = entry.get("timestamp", "")
            time_str = _format_ist(ts)

            node = entry.get("node", "")
            node_labels = {
                "enrich": "Company enrichment",
                "score": "Lead scored",
                "classify": "Classification applied",
                "route": "Routing decision",
                "draft": "Email draft created",
            }
            label = node_labels.get(node, node)

            output = entry.get("output", {})
            detail = ""
            if node == "classify":
                detail = f" - {output.get('label', '')}"
            elif node == "route":
                detail = f" - {output.get('routed_to', '')}"
            elif node == "score":
                detail = f" - {output.get('total', '')}/100"

            st.write(f"**{time_str}** - {label}{detail}")
    else:
        st.info("No audit trail entries for this lead.")


def _handle_approval(lead_data: dict, result: dict, action: str, idx: int, edited_body: str | None = None) -> None:
    approval = {
        "action": action,
        "edited_body": edited_body if action == "edit" else None,
        "rep_id": "streamlit-rep",
        "timestamp": datetime.now().isoformat(),
    }

    result["approval"] = approval

    if action in ("approve", "edit"):
        from tools.email_send import email_send
        draft = result.get("draft", {})
        body = edited_body if edited_body else draft.get("body", "")

        try:
            send_result = email_send(
                to=lead_data["email"],
                subject=draft.get("subject", ""),
                body=body,
                lead_name=lead_data["name"],
                lead_company=lead_data["company"],
                approval_action=action,
            )
            st.success(f"Email sent to {lead_data['email']}!")
        except Exception as e:
            st.error(f"Failed to send email: {e}")
    else:
        from tools.crm_write import crm_write
        crm_write(
            lead_id=lead_data["email"],
            status="rejected",
            reason="Rep rejected the draft",
            lead_name=lead_data["name"],
            lead_email=lead_data["email"],
            lead_company=lead_data["company"],
        )
        st.info("Lead archived. No email sent.")


# ---- Audit view ----

def render_audit_view() -> None:
    st.subheader("Audit Log")

    log_entries = read_audit_log(limit=100)

    if not log_entries:
        st.info("No audit log entries yet.")
        return

    search = st.text_input("Search by name, company, or action", placeholder="Type to filter...")

    filtered = log_entries
    if search:
        search_lower = search.lower()
        filtered = [
            e for e in log_entries
            if search_lower in (e.get("lead_name", "") or "").lower()
            or search_lower in (e.get("lead_company", "") or "").lower()
            or search_lower in (e.get("action", "") or "").lower()
        ]

    st.write(f"Showing {len(filtered)} of {len(log_entries)} entries")

    for entry in filtered:
        with st.container():
            ts = entry.get("timestamp", "")
            time_str = _format_ist(ts)

            cols = st.columns([1, 2, 1.5, 2, 1.5])
            with cols[0]:
                st.caption(time_str)
            with cols[1]:
                st.write(entry.get("lead_name", ""))
            with cols[2]:
                st.write(entry.get("lead_company", ""))
            with cols[3]:
                action = entry.get("action", "")
                if "email_sent" in action:
                    st.success(f"Email Sent")
                elif "nurture" in action:
                    st.warning(f"Nurture")
                elif "archived" in action or "disqualified" in action or "rejected" in action:
                    st.info(f"Archived")
                else:
                    st.write(action)
            with cols[4]:
                reason = entry.get("reason", "")
                if reason:
                    with st.expander("Details"):
                        st.write(f"Reason: {reason}")
                        details = entry.get("details", "")
                        if details:
                            st.write(f"Details: {details}")
            st.divider()


# ---- Main app ----

def main() -> None:
    st.set_page_config(
        page_title="LeadPilot - Lead Qualification Agent",
        page_icon="",
        layout="wide",
    )

    st.title("LeadPilot")
    st.caption("Lead Qualification & Outreach Agent")

    init_session_state()

    tab_dashboard, tab_inbox, tab_detail, tab_audit = st.tabs(["Dashboard", "Inbox", "Lead Detail", "Audit Log"])

    with tab_dashboard:
        render_dashboard()

    with tab_inbox:
        render_inbox()

    with tab_detail:
        render_lead_detail()

    with tab_audit:
        render_audit_view()


if __name__ == "__main__":
    main()
