"""Streamlit UI for the Lead Qualification Agent.

Three views:
1. Inbox - table of leads with score + classification
2. Lead detail - full details with Approve/Edit/Reject
3. Audit log - searchable history
"""

from __future__ import annotations

import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.state import Lead, AgentState, ApprovalDecision, EmailDraft
from agent.graph import create_graph, run_agent
from tools.crm_write import read_audit_log


# ---- Session state initialization ----
def init_session_state() -> None:
    """Initialize Streamlit session state."""
    if "leads" not in st.session_state:
        st.session_state.leads = []
    if "results" not in st.session_state:
        st.session_state.results = {}
    if "current_index" not in st.session_state:
        st.session_state.current_index = None


# ---- Lead processing ----
def process_lead(lead_dict: dict) -> dict:
    """Process a lead through the agent pipeline."""
    app = create_graph()
    lead = Lead(**lead_dict)
    input_state = {"lead": lead}
    result = app.invoke(input_state)
    return result


# ---- Lead form ----
def render_lead_form() -> None:
    """Render the new lead input form."""
    with st.expander("➕ Add New Lead", expanded=False):
        with st.form("lead_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Name*", placeholder="e.g. John Smith")
                company = st.text_input("Company*", placeholder="e.g. Acme Corp")
                role = st.text_input("Role", placeholder="e.g. CTO")
            with col2:
                email = st.text_input("Email*", placeholder="e.g. john@acme.com")
                message = st.text_area("Message", placeholder="How did they hear about you? What are they interested in?", height=100)

            submitted = st.form_submit_button("Submit Lead", type="primary", use_container_width=True)

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
    """Render the inbox table of leads."""
    st.subheader("📥 Inbox")

    if not st.session_state.leads:
        st.info("No leads yet. Add a lead using the form above.")
        return

    # Build table data
    table_data = []
    for i, lead_data in enumerate(st.session_state.leads):
        result = st.session_state.results.get(lead_data["email"], {})
        classification = result.get("classification", {})
        score = result.get("score", {})
        enrichment = result.get("enrichment", {})

        label = classification.get("label", "PENDING")
        total_score = score.get("total", "N/A")
        industry = enrichment.get("industry", "?")

        # Color coding
        if label == "HOT":
            badge = "🔴 HOT"
        elif label == "NURTURE":
            badge = "🟡 NURTURE"
        elif label == "DISQUALIFY":
            badge = "⚫ DISQUALIFY"
        else:
            badge = "⚪ PENDING"

        table_data.append({
            "": i + 1,
            "Name": lead_data["name"],
            "Company": lead_data["company"],
            "Industry": industry,
            "Score": total_score,
            "Status": badge,
        })

    st.data_editor(
        table_data,
        use_container_width=True,
        hide_index=True,
        column_config={
            "": st.column_config.NumberColumn(width=40),
            "Status": st.column_config.TextColumn(width=130),
        },
        disabled=True,
    )


# ---- Lead detail view ----
def render_lead_detail() -> None:
    """Render the detail view for a selected lead."""
    st.subheader("🔍 Lead Detail")

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

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📋 Lead Info")
        st.write(f"**Name:** {lead_data['name']}")
        st.write(f"**Email:** {lead_data['email']}")
        st.write(f"**Company:** {lead_data['company']}")
        st.write(f"**Role:** {lead_data.get('role', 'N/A') or 'N/A'}")
        st.write(f"**Message:** {lead_data.get('message', 'N/A') or 'N/A'}")

        enrichment = result.get("enrichment", {})
        if enrichment:
            st.markdown("#### 📊 Enrichment")
            st.write(f"**Industry:** {enrichment.get('industry', 'N/A')}")
            st.write(f"**Employees:** {enrichment.get('employee_count', 'N/A')}")
            st.write(f"**Revenue:** {enrichment.get('revenue_estimate', 'N/A')}")
            st.write(f"**Buying Signal:** {enrichment.get('buying_signal', 'N/A')}")
            st.write(f"**Source:** {enrichment.get('source', 'N/A')}")

    with col2:
        score = result.get("score", {})
        classification = result.get("classification", {})

        if score:
            st.markdown("#### 🎯 Score Breakdown")
            st.write(f"**Industry Match:** {score.get('industry_match', 0)} / 30")
            st.write(f"**Company Size:** {score.get('company_size', 0)} / 25")
            st.write(f"**Role Match:** {score.get('role_match', 0)} / 25")
            st.write(f"**Buying Signal:** {score.get('buying_signal', 0)} / 20")
            st.write(f"**Total:** {score.get('total', 0)} / 100")

        if classification:
            label = classification.get("label", "UNKNOWN")
            if label == "HOT":
                st.error(f"**Status:** 🔴 {label}")
            elif label == "NURTURE":
                st.warning(f"**Status:** 🟡 {label}")
            else:
                st.info(f"**Status:** ⚫ {label}")

            st.write(f"**Reason:** {classification.get('reason', 'N/A')}")

        # Injection flag
        if result.get("injection_flagged"):
            st.error("⚠️ **Prompt injection detected!** Message contained suspicious patterns.")

    # ---- Email Draft & Approval ----
    draft = result.get("draft")
    approval = result.get("approval")

    if draft:
        st.markdown("---")
        st.markdown("#### ✉️ Draft Email")

        st.write(f"**Subject:** {draft.get('subject', 'N/A')}")
        st.text_area("Body", draft.get("body", ""), height=200, key=f"email_body_{selected_idx}")

        grounded_on = draft.get("grounded_on", [])
        if grounded_on:
            with st.expander("📎 Grounded On (enrichment facts used)"):
                for fact in grounded_on:
                    st.write(f"- {fact}")

        # Approval controls
        st.markdown("#### 👤 Approval Required")
        st.caption("No email will be sent until you approve.")

        col_a, col_b, col_c = st.columns([1, 1, 1])

        with col_a:
            if st.button("✅ Approve", key=f"approve_{selected_idx}", type="primary", use_container_width=True):
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
            if st.button("✏️ Approve with Edit", key=f"edit_{selected_idx}", use_container_width=True):
                _handle_approval(lead_data, result, "edit", selected_idx, edited_body)
                st.rerun()

        with col_c:
            if st.button("❌ Reject", key=f"reject_{selected_idx}", use_container_width=True):
                _handle_approval(lead_data, result, "reject", selected_idx)
                st.rerun()

    elif classification.get("label") == "HOT":
        st.info("Draft not yet generated. The lead may still be processing.")

    # Show injection warning if flagged
    if result.get("injection_flagged"):
        st.markdown("---")
        st.error(
            "⚠️ **Injection Flagged** - The lead's message contained patterns "
            "that suggest a prompt injection attempt. The buying signal was "
            "scored as neutral. This lead should be manually reviewed."
        )


def _handle_approval(lead_data: dict, result: dict, action: str, idx: int, edited_body: str | None = None) -> None:
    """Handle an approval decision from the rep."""
    approval = {
        "action": action,
        "edited_body": edited_body if action == "edit" else None,
        "rep_id": "streamlit-rep",
        "timestamp": datetime.now().isoformat(),
    }

    # Update the result with approval
    result["approval"] = approval

    # If approved/edited, process through the email send gate
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
            st.success(f"✅ Email sent to {lead_data['email']}!")
        except Exception as e:
            st.error(f"Failed to send email: {e}")
    else:
        # Rejected - archive
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
    """Render the audit log view."""
    st.subheader("📜 Audit Log")

    log_entries = read_audit_log(limit=100)

    if not log_entries:
        st.info("No audit log entries yet.")
        return

    # Filter controls
    search = st.text_input("🔍 Search by name, company, or action", placeholder="Type to filter...")

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
            cols = st.columns([2, 1.5, 1.5, 2, 1])
            with cols[0]:
                st.caption(entry.get("timestamp", "")[:19])
            with cols[1]:
                st.write(entry.get("lead_name", ""))
            with cols[2]:
                st.write(entry.get("lead_company", ""))
            with cols[3]:
                action = entry.get("action", "")
                if "email_sent" in action:
                    st.success(f"📧 {action}")
                elif "nurture" in action:
                    st.warning(f"🟡 {action}")
                elif "archived" in action or "disqualified" in action or "rejected" in action:
                    st.info(f"⚫ {action}")
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
    """Main Streamlit application."""
    st.set_page_config(
        page_title="LeadPilot - Lead Qualification Agent",
        page_icon="🎯",
        layout="wide",
    )

    st.title("🎯 LeadPilot")
    st.caption("Lead Qualification & Outreach Agent")

    init_session_state()

    # Tabs
    tab_inbox, tab_detail, tab_audit = st.tabs(["📥 Inbox", "🔍 Lead Detail", "📜 Audit Log"])

    with tab_inbox:
        render_lead_form()
        render_inbox()

    with tab_detail:
        render_lead_detail()

    with tab_audit:
        render_audit_view()


if __name__ == "__main__":
    main()