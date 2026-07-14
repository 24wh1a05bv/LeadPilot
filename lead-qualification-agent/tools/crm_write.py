"""Gated CRM write tool - only callable when approval state permits."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
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


def _log_action(lead_name: str, lead_email: str, lead_company: str,
                action: str, reason: str | None, details: str | None = None) -> None:
    """Record an action in the audit log."""
    conn = _get_db()
    conn.execute(
        "INSERT INTO audit_log (timestamp, lead_name, lead_email, lead_company, action, reason, details) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), lead_name, lead_email, lead_company, action, reason, details)
    )
    conn.commit()
    conn.close()


def crm_write(lead_id: str, status: str, reason: str | None = None,
              lead_name: str = "", lead_email: str = "", lead_company: str = "",
              gated: bool = True) -> dict:
    """Write lead status to CRM (gated).

    In production, this would call a CRM API. Here it logs to SQLite.

    Args:
        lead_id: Identifier for the lead.
        status: Status to set (e.g. 'nurture', 'disqualified', 'contacted').
        reason: Classification reason.
        lead_name: Lead's name (for logging).
        lead_email: Lead's email (for logging).
        lead_company: Lead's company (for logging).
        gated: If True, this is a gated call that requires proper authorization.

    Returns:
        Dict with success status and message.
    """
    _log_action(lead_name, lead_email, lead_company, f"crm_write:{status}", reason)

    return {
        "success": True,
        "lead_id": lead_id,
        "status": status,
        "reason": reason,
        "logged": True
    }


def read_audit_log(limit: int = 50) -> list[dict]:
    """Read recent entries from the audit log."""
    conn = _get_db()
    cursor = conn.execute(
        "SELECT timestamp, lead_name, lead_email, lead_company, action, reason, details "
        "FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
    )
    rows = [
        {
            "timestamp": row[0],
            "lead_name": row[1],
            "lead_email": row[2],
            "lead_company": row[3],
            "action": row[4],
            "reason": row[5],
            "details": row[6]
        }
        for row in cursor.fetchall()
    ]
    conn.close()
    return rows