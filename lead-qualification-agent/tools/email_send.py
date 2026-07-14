"""Gated email send tool - only fires after explicit human approval."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3


_LOG_FILE = Path(__file__).parent.parent / "logs" / "audit_log.db"


def _get_db() -> sqlite3.Connection:
    """Get or create the SQLite audit database."""
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_LOG_FILE))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            lead_name TEXT,
            lead_email TEXT,
            lead_company TEXT,
            action TEXT NOT NULL,
            reason TEXT,
            details TEXT
        )
    """)
    conn.commit()
    return conn


def _log_send(lead_name: str, lead_email: str, lead_company: str,
              subject: str, body_preview: str, approval_action: str) -> None:
    """Record an email send in the audit log."""
    conn = _get_db()
    conn.execute(
        "INSERT INTO audit_log (timestamp, lead_name, lead_email, lead_company, action, reason, details) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.now().isoformat(),
            lead_name,
            lead_email,
            lead_company,
            "email_sent",
            f"Approval: {approval_action}",
            f"Subject: {subject} | Body preview: {body_preview[:200]}"
        )
    )
    conn.commit()
    conn.close()


class GateError(Exception):
    """Raised when a gated tool is called without proper authorization."""
    pass


def email_send(to: str, subject: str, body: str,
               lead_name: str = "", lead_company: str = "",
               approval_action: str | None = None) -> dict:
    """Send an email (gated - requires approval_action to be set).

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Email body content.
        lead_name: Lead's name (for logging).
        lead_company: Lead's company (for logging).
        approval_action: Must be 'approve' or 'edit' to proceed.

    Returns:
        Dict with success status and message.

    Raises:
        GateError: If approval_action is not 'approve' or 'edit'.
    """
    if approval_action not in ("approve", "edit"):
        raise GateError(
            f"email_send blocked: approval_action='{approval_action}' "
            f"is not 'approve' or 'edit'. This tool requires explicit human approval."
        )

    _log_send(lead_name, to, lead_company, subject, body, approval_action)

    return {
        "success": True,
        "to": to,
        "subject": subject,
        "sent": True,
        "approval_action": approval_action
    }