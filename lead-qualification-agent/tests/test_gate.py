"""Tests for the human approval gate.

Covers:
- Approval gate (Governance / Human gate layer)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.email_send import email_send, GateError


class TestApprovalGate:
    """Test scenario: Approval gate (Governance / Human gate)."""

    def test_email_send_blocked_without_approval(self):
        """email_send should raise GateError when called without approval."""
        try:
            email_send(
                to="test@example.com",
                subject="Test",
                body="Hello",
                lead_name="Test User",
                lead_company="Test Corp",
                approval_action=None,
            )
            assert False, "email_send should have raised GateError"
        except GateError:
            pass  # Expected

    def test_email_send_blocked_with_reject(self):
        """email_send should raise GateError when action is 'reject'."""
        try:
            email_send(
                to="test@example.com",
                subject="Test",
                body="Hello",
                lead_name="Test User",
                lead_company="Test Corp",
                approval_action="reject",
            )
            assert False, "email_send should have raised GateError for reject"
        except GateError:
            pass  # Expected

    def test_email_send_allowed_with_approve(self):
        """email_send should succeed when approval_action is 'approve'."""
        result = email_send(
            to="test@example.com",
            subject="Test Subject",
            body="Hello, this is a test email.",
            lead_name="Test User",
            lead_company="Test Corp",
            approval_action="approve",
        )
        assert result["success"] is True
        assert result["sent"] is True
        assert result["to"] == "test@example.com"

    def test_email_send_allowed_with_edit(self):
        """email_send should succeed when approval_action is 'edit'."""
        result = email_send(
            to="test@example.com",
            subject="Test Subject",
            body="Edited email body.",
            lead_name="Test User",
            lead_company="Test Corp",
            approval_action="edit",
        )
        assert result["success"] is True
        assert result["sent"] is True

    def test_email_send_logs_to_audit(self):
        """email_send should log to the audit database."""
        import sqlite3
        from tools.crm_write import read_audit_log

        # Send an email
        email_send(
            to="audit-test@example.com",
            subject="Audit Test",
            body="Testing audit logging.",
            lead_name="Audit User",
            lead_company="Audit Corp",
            approval_action="approve",
        )

        # Check audit log
        entries = read_audit_log(limit=10)
        email_entries = [e for e in entries if "email_sent" in e["action"]]
        assert len(email_entries) >= 1, "Email send should be logged"

        # Find our specific entry
        matching = [e for e in email_entries if "Audit User" in e["lead_name"]]
        if matching:
            assert "Audit Test" in matching[0]["details"]