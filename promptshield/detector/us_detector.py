"""Regex-based detector for US-specific PII patterns.

Supported entity types
----------------------
ssn          US Social Security Number (validated: no all-zero segments).
us_passport  US passport book number: 1 alpha + 8 digits.
us_ein       Employer Identification Number: XX-XXXXXXX.
"""

import re
from typing import Dict, List

from .base import BaseDetector, DetectedEntity
from .regex_detector import _resolve_overlaps

_RAW_PATTERNS: Dict[str, List[str]] = {
    "ssn": [
        # 3-2-4 pattern; rejects 000-xx-xxxx, 666-xx-xxxx, 9xx-xx-xxxx,
        # xxx-00-xxxx, xxx-xx-0000 (ITIN / invalid blocks).
        r"\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b",
    ],
    "us_passport": [
        # US passport: 1 alpha + 8 digits (distinct from Indian A + 7 digits)
        r"\b[A-Z][0-9]{8}\b",
    ],
    "us_ein": [
        # EIN: two digits (not 00) + hyphen (optional) + seven digits
        r"\b(?!00)\d{2}-?\d{7}\b",
    ],
}

_COMPILED: Dict[str, List[re.Pattern]] = {
    entity_type: [re.compile(p) for p in patterns]
    for entity_type, patterns in _RAW_PATTERNS.items()
}


class USDetector(BaseDetector):
    """
    Regex-based detector for US-specific PII.

    Detects the following entity types:

    * ``ssn``          — Social Security Number (rejects all-zero segments)
    * ``us_passport``  — US passport number (e.g. ``A12345678``)
    * ``us_ein``       — Employer Identification Number (e.g. ``12-3456789``)
    """

    @property
    def supported_types(self) -> List[str]:
        return list(_COMPILED.keys())

    def detect(self, text: str) -> List[DetectedEntity]:
        """
        Scan *text* for US-specific PII.

        Args:
            text: The input string to scan.

        Returns:
            Non-overlapping list of :class:`~promptshield.detector.base.DetectedEntity`
            instances sorted by start position.
        """
        entities: List[DetectedEntity] = []
        for entity_type, patterns in _COMPILED.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    entities.append(
                        DetectedEntity(
                            entity_type=entity_type,
                            value=match.group(),
                            start=match.start(),
                            end=match.end(),
                        )
                    )
        return _resolve_overlaps(entities)
