"""Masking logic for sensitive entity values."""

import re
from typing import Callable, Dict, List

from ..detector.base import DetectedEntity


# ---------------------------------------------------------------------------
# Per-type masking helpers
# ---------------------------------------------------------------------------

def _mask_email(value: str) -> str:
    """Mask the local-part of an email, preserving the domain.

    Example: ``john.doe@example.com`` → ``j***@example.com``
    """
    parts = value.split("@", 1)
    if len(parts) != 2:
        return "***@***.***"
    local, domain = parts
    masked_local = (local[0] + "***") if len(local) > 1 else "***"
    return f"{masked_local}@{domain}"


def _mask_phone(value: str) -> str:
    """Mask a phone number, keeping only the last four digits.

    Example: ``555-867-5309`` → ``***-***-5309``
    """
    digits = re.sub(r"\D", "", value)
    last_four = digits[-4:] if len(digits) >= 4 else "****"
    return f"***-***-{last_four}"


def _mask_credit_card(value: str) -> str:
    """Mask a credit card number, keeping only the last four digits.

    Example: ``4111-1111-1111-1111`` → ``****-****-****-1111``
    """
    digits = re.sub(r"\D", "", value)
    last_four = digits[-4:] if len(digits) >= 4 else "****"
    return f"****-****-****-{last_four}"


def _mask_api_key(value: str) -> str:
    """Mask an API key / token, keeping first 4 and last 4 characters.

    Example: ``sk-abcdefgh1234567890`` → ``sk-a...7890``
    """
    clean = value.strip()
    if len(clean) <= 8:
        return "***"
    return f"{clean[:4]}...{clean[-4:]}"


def _mask_generic(value: str) -> str:
    """Generic masking: first 2 + last 2 characters, rest replaced with ``***``.

    Example: ``MySecret`` → ``My***et``
    """
    if len(value) <= 4:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


# ---------------------------------------------------------------------------
# India-specific masking helpers
# ---------------------------------------------------------------------------

def _mask_in_aadhaar(value: str) -> str:
    """Mask Aadhaar, keeping only the last 4 digits.

    Example: ``2345 6789 0123`` → ``XXXX-XXXX-0123``
    """
    digits = re.sub(r"[\s\-]", "", value)
    last_four = digits[-4:] if len(digits) >= 4 else "****"
    return f"XXXX-XXXX-{last_four}"


def _mask_in_pan(value: str) -> str:
    """Mask PAN card, showing first 2 and last 1 characters.

    Example: ``ABCDE1234F`` → ``AB*******F``
    """
    if len(value) < 3:
        return "***"
    return f"{value[:2]}{'*' * (len(value) - 3)}{value[-1]}"


def _mask_in_phone(value: str) -> str:
    """Mask Indian phone number, keeping only last 4 digits.

    Example: ``+91 98765 43210`` → ``+91-***-***-3210``
    """
    digits = re.sub(r"\D", "", value)
    last_four = digits[-4:] if len(digits) >= 4 else "****"
    return f"+91-***-***-{last_four}"


def _mask_in_passport(value: str) -> str:
    """Mask Indian passport number, keeping only the first letter.

    Example: ``A1234567`` → ``A*******``
    """
    if not value:
        return "***"
    return f"{value[0]}{'*' * (len(value) - 1)}"


def _mask_in_voter_id(value: str) -> str:
    """Mask Voter ID (EPIC), keeping the 3-letter state prefix.

    Example: ``ABC1234567`` → ``ABC*******``
    """
    if len(value) <= 3:
        return "***"
    return f"{value[:3]}{'*' * (len(value) - 3)}"


def _mask_in_ifsc(value: str) -> str:
    """Mask IFSC code, keeping only the 4-letter bank code and the mandatory zero.

    Example: ``SBIN0001234`` → ``SBIN0******``
    """
    if len(value) <= 5:
        return "***"
    return f"{value[:5]}{'*' * (len(value) - 5)}"


def _mask_in_gstin(value: str) -> str:
    """Mask GSTIN, keeping only the 2-digit state code.

    Example: ``27ABCDE1234F1Z5`` → ``27*************``
    """
    if len(value) <= 2:
        return "***"
    return f"{value[:2]}{'*' * (len(value) - 2)}"


# ---------------------------------------------------------------------------
# US-specific masking helpers
# ---------------------------------------------------------------------------

def _mask_ssn(value: str) -> str:
    """Mask SSN, keeping only the last four digits.

    Example: ``123-45-6789`` → ``***-**-6789``
    """
    digits = re.sub(r"\D", "", value)
    last_four = digits[-4:] if len(digits) >= 4 else "****"
    return f"***-**-{last_four}"


def _mask_us_passport(value: str) -> str:
    """Mask a US passport number, keeping only the leading letter.

    Example: ``A12345678`` → ``A********``
    """
    if len(value) <= 1:
        return "***"
    return f"{value[0]}{'*' * (len(value) - 1)}"


def _mask_us_ein(value: str) -> str:
    """Mask an EIN, keeping only the 2-digit prefix.

    Example: ``12-3456789`` → ``12-*******``
    """
    digits = re.sub(r"\D", "", value)
    prefix = digits[:2] if len(digits) >= 2 else "**"
    return f"{prefix}-*******"


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_MASKERS: Dict[str, Callable[[str], str]] = {
    "email": _mask_email,
    "phone": _mask_phone,
    "credit_card": _mask_credit_card,
    "api_key": _mask_api_key,
    # India-specific
    "in_aadhaar": _mask_in_aadhaar,
    "in_pan": _mask_in_pan,
    "in_phone": _mask_in_phone,
    "in_passport": _mask_in_passport,
    "in_voter_id": _mask_in_voter_id,
    "in_ifsc": _mask_in_ifsc,
    "in_gstin": _mask_in_gstin,
    # US-specific
    "ssn": _mask_ssn,
    "us_passport": _mask_us_passport,
    "us_ein": _mask_us_ein,
}


def mask_value(value: str, entity_type: str) -> str:
    """
    Apply the appropriate mask for the given entity type.

    Falls back to :func:`_mask_generic` for unknown entity types, making the
    masking layer safe to use with custom detectors.

    Args:
        value: The original sensitive string.
        entity_type: The entity category label (e.g. ``"email"``).

    Returns:
        A masked version of *value*.
    """
    masker = _MASKERS.get(entity_type, _mask_generic)
    return masker(value)


def apply_masks(text: str, entities: List[DetectedEntity]) -> str:
    """
    Replace each entity's value in *text* with its masked equivalent.

    Entities are processed in reverse order (right → left) so that earlier
    character positions remain valid after each substitution.

    Args:
        text: The original input text.
        entities: Entities whose values should be masked.

    Returns:
        A new string with all entity values replaced by masked versions.
    """
    # Process right-to-left to keep earlier indices stable.
    sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)
    result = text
    for entity in sorted_entities:
        masked = mask_value(entity.value, entity.entity_type)
        result = result[: entity.start] + masked + result[entity.end :]
    return result
