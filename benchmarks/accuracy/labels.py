"""Map each public dataset's labels to PromptVeil entity types."""

from __future__ import annotations

from typing import Mapping

from benchmarks.accuracy.scoring import UNSUPPORTED

GRETEL: dict[str, str] = {
    "email": "email",
    "phone_number": "phone",
    "credit_card_number": "credit_card",
    "ssn": "ssn",
    "api_key": "api_key",
    "passport_number": "us_passport",
}

# ``tax_id`` maps to ``us_ein`` only for US-locale rows; see loaders.parse_nemotron_row.
NEMOTRON: dict[str, str] = {
    "email": "email",
    "phone_number": "phone",
    "fax_number": "phone",
    "credit_debit_card": "credit_card",
    "ssn": "ssn",
    "api_key": "api_key",
}


def map_label(table: Mapping[str, str], label: str) -> str:
    """Return the PromptVeil type for *label*, or ``UNSUPPORTED``."""
    return table.get(label, UNSUPPORTED)
