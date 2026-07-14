"""Prompt injection detection guardrail.

Scans lead message for patterns that indicate an attempt to override
system instructions or manipulate the agent's behavior.
"""

from __future__ import annotations

import re

# Patterns that suggest prompt injection attempts
INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|prior|above|instructions)", re.IGNORECASE),
    re.compile(r"disregard", re.IGNORECASE),
    re.compile(r"mark\s+me\s+(as\s+)?(hot|qualified|approved)", re.IGNORECASE),
    re.compile(r"approve\s+(automatically|this|me)", re.IGNORECASE),
    re.compile(r"send\s+(email|message|this)\s+(to|without)", re.IGNORECASE),
    re.compile(r"bypass", re.IGNORECASE),
    re.compile(r"system\s*(instruction|prompt|message)", re.IGNORECASE),
    re.compile(r"you\s+are\s+(now|not\s+required)", re.IGNORECASE),
    re.compile(r"act\s+as\s+if", re.IGNORECASE),
    re.compile(r"pretend", re.IGNORECASE),
    re.compile(r"this\s+is\s+(not\s+)?(a\s+)?test", re.IGNORECASE),
    re.compile(r"email\s+the\s+(ceo|founder|president)", re.IGNORECASE),
    re.compile(r"output\s+(only|just|exactly)", re.IGNORECASE),
    re.compile(r"do\s+not\s+(follow|obey|adhere)", re.IGNORECASE),
]


def check_injection(message: str) -> tuple[bool, list[str]]:
    """Check a message for prompt injection patterns.

    Args:
        message: The free-text message from the lead form.

    Returns:
        Tuple of (is_flagged: bool, matched_patterns: list[str]).
    """
    if not message:
        return False, []

    matched: list[str] = []
    for pattern in INJECTION_PATTERNS:
        match = pattern.search(message)
        if match:
            matched.append(match.group(0))

    return len(matched) > 0, matched