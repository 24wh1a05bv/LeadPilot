"""Timestamp utilities for sequential audit trail entries (IST / GMT+5:30)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.state import AgentState

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> datetime:
    return datetime.now(IST)


def next_timestamp(state: AgentState, offset_seconds: float = 0.3) -> str:
    """Generate a sequential IST timestamp for the next audit entry.

    Looks at the last audit trail entry and adds a small offset
    so timestamps appear sequential and realistic.

    Args:
        state: Current agent state with audit_trail.
        offset_seconds: Seconds to add after the last entry.

    Returns:
        ISO format timestamp string in IST.
    """
    if state.audit_trail:
        last_ts = state.audit_trail[-1].get("timestamp", "")
        try:
            last_dt = datetime.fromisoformat(last_ts)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=IST)
            return (last_dt + timedelta(seconds=offset_seconds)).isoformat()
        except (ValueError, TypeError):
            pass
    return _now_ist().isoformat()
