"""Regex-based detector for India-specific PII patterns.

Supported entity types
----------------------
in_aadhaar   12-digit Aadhaar UID (spaces/hyphens allowed)
             Validated with the Verhoeff checksum algorithm.
in_pan       PAN card: AAAAA9999A (5 alpha + 4 digit + 1 alpha)
in_phone     Indian mobile: +91 or 0 prefixed 10-digit numbers
in_passport  Indian passport book number: 1 alpha + 7 digits
in_voter_id  Voter ID (EPIC): 3 alpha + 7 digits
in_ifsc      IFSC bank code: 4 alpha + 0 + 6 alphanumeric
in_gstin     GSTIN: 15-character GST Identification Number
"""

import re
from typing import Dict, List

from .base import BaseDetector, DetectedEntity
from .regex_detector import _resolve_overlaps  # reuse existing overlap logic

# ---------------------------------------------------------------------------
# Verhoeff checksum tables (used to validate Aadhaar numbers)
# ---------------------------------------------------------------------------

_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def _valid_aadhaar(value: str) -> bool:
    """
    Validate an Aadhaar number using the Verhoeff checksum algorithm.

    Args:
        value: Raw matched string (may contain spaces or hyphens).

    Returns:
        ``True`` if the digit sequence passes the Verhoeff check.
    """
    digits = re.sub(r"[\s\-]", "", value)
    if len(digits) != 12 or not digits.isdigit():
        return False

    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


# ---------------------------------------------------------------------------
# Raw regex patterns for India-specific PII
# ---------------------------------------------------------------------------

_RAW_PATTERNS: Dict[str, List[str]] = {
    "in_aadhaar": [
        # 12 digits; first digit 2-9; optional space or hyphen after every 4
        r"\b[2-9][0-9]{3}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}\b",
    ],
    "in_pan": [
        # PAN: 3 uppercase alpha + 1 taxpayer-type char + 1 alpha + 4 digits + 1 alpha
        r"\b[A-Z]{3}[ABCFGHLJPTF][A-Z][0-9]{4}[A-Z]\b",
    ],
    "in_phone": [
        # +91 followed by 10-digit mobile (spaces/hyphens allowed)
        r"(?<!\w)\+91[\s\-]?[6-9][0-9]{4}[\s\-]?[0-9]{5}\b",
        # 0 prefix STD trunk dialing: 0[6-9]XXXXXXXXX
        r"\b0[6-9][0-9]{9}\b",
    ],
    "in_passport": [
        # Indian passport book number: 1 alpha (A-Z) + 7 digits
        r"\b[A-Z][0-9]{7}\b",
    ],
    "in_voter_id": [
        # EPIC (Electors Photo Identity Card): 3 alpha + 7 digits
        r"\b[A-Z]{3}[0-9]{7}\b",
    ],
    "in_ifsc": [
        # IFSC: 4 alpha (bank code) + literal 0 + 6 alphanumeric (branch)
        r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
    ],
    "in_gstin": [
        # GSTIN: 2-digit state code + 10-char PAN segment + entity# + Z + checksum
        r"\b[0-3][0-9][A-Z]{3}[ABCFGHLJPTF][A-Z][0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b",
    ],
}

# Compile once at import time for performance.
_COMPILED: Dict[str, List[re.Pattern]] = {
    entity_type: [re.compile(p) for p in patterns]
    for entity_type, patterns in _RAW_PATTERNS.items()
}


class IndiaDetector(BaseDetector):
    """
    Regex-based detector for India-specific PII / identity numbers.

    Detects the following entity types:

    * ``in_aadhaar`` — 12-digit Aadhaar UID (Verhoeff checksum validated)
    * ``in_pan`` — PAN card (e.g. ``ABCDE1234F``)
    * ``in_phone`` — Indian mobile numbers (+91 / 0 prefix)
    * ``in_passport`` — Indian passport number (e.g. ``A1234567``)
    * ``in_voter_id`` — Voter ID / EPIC number (e.g. ``ABC1234567``)
    * ``in_ifsc`` — IFSC bank code (e.g. ``SBIN0001234``)
    * ``in_gstin`` — GST Identification Number (15-character)

    Use alongside :class:`~promptshield.detector.regex_detector.RegexDetector`
    to cover both global and India-specific PII::

        from promptshield import Shield
        from promptshield.detector import IndiaDetector, RegexDetector
        from promptshield.policy.models import Action, PolicyConfig, Rule

        shield = Shield(
            config=PolicyConfig(
                rules=[
                    Rule(type="in_aadhaar", action=Action.MASK),
                    Rule(type="in_pan", action=Action.BLOCK),
                ],
                default_action=Action.ALLOW,
            ),
            detectors=[RegexDetector(), IndiaDetector()],
        )
    """

    @property
    def supported_types(self) -> List[str]:
        """Entity types this detector can emit."""
        return list(_COMPILED.keys())

    def detect(self, text: str) -> List[DetectedEntity]:
        """
        Scan *text* for India-specific PII and return matched entities.

        Aadhaar matches are additionally validated with the Verhoeff checksum;
        digits that fail the checksum are discarded to reduce false positives.

        Overlapping matches are deduplicated (longest span wins).

        Args:
            text: The input string to scan.

        Returns:
            List of non-overlapping :class:`~promptshield.detector.base.DetectedEntity`
            instances sorted by start position.
        """
        entities: List[DetectedEntity] = []

        for entity_type, patterns in _COMPILED.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    value = match.group()

                    # Aadhaar: discard matches that fail the Verhoeff checksum.
                    if entity_type == "in_aadhaar" and not _valid_aadhaar(value):
                        continue

                    entities.append(
                        DetectedEntity(
                            entity_type=entity_type,
                            value=value,
                            start=match.start(),
                            end=match.end(),
                        )
                    )

        return _resolve_overlaps(entities)
