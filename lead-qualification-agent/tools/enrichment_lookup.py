"""Mock company enrichment lookup tool."""

from __future__ import annotations

import json
import os
from pathlib import Path

from agent.state import Enrichment


def _load_companies() -> dict:
    """Load mock companies from JSON data file."""
    data_path = Path(__file__).parent.parent / "data" / "mock_companies.json"
    with open(data_path) as f:
        return json.load(f)["companies"]


def enrichment_lookup(company: str) -> Enrichment | None:
    """Look up company data from the mocked dataset.

    Args:
        company: Company name to look up.

    Returns:
        Enrichment object if found, None otherwise.
    """
    companies = _load_companies()
    # Case-insensitive lookup
    for name, data in companies.items():
        if name.lower() == company.lower():
            return Enrichment(
                industry=data["industry"],
                employee_count=data["employee_count"],
                revenue_estimate=data["revenue_estimate"],
                tech_stack=data["tech_stack"],
                buying_signal=data["buying_signal"],
                source=f"mock_companies.json -> {name}",
            )
    return None