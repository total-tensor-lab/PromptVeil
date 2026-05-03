"""Regex-based detector for common PII and secret patterns."""

import re
from typing import Dict, List

from .base import BaseDetector, DetectedEntity

# ---------------------------------------------------------------------------
# Compiled pattern registry
# Each key maps to a list of compiled patterns that emit that entity type.
# ---------------------------------------------------------------------------
_RAW_PATTERNS: Dict[str, List[str]] = {
    "email": [
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    ],
    "phone": [
        # North-American: (555) 867-5309 / 555.867.5309 / +1 555-867-5309
        r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
        # International E.164: +442071234567 or +44 7911 123456
        r"(?<!\w)\+[1-9][0-9]{7,14}\b",
    ],
    "credit_card": [
        # Visa (16 digit)
        r"\b4[0-9]{3}[- ]?[0-9]{4}[- ]?[0-9]{4}[- ]?[0-9]{4}\b",
        # Mastercard (16 digit)
        r"\b5[1-5][0-9]{2}[- ]?[0-9]{4}[- ]?[0-9]{4}[- ]?[0-9]{4}\b",
        # Amex (15 digit)
        r"\b3[47][0-9]{2}[- ]?[0-9]{6}[- ]?[0-9]{5}\b",
        # Discover (16 digit)
        r"\b6(?:011|5[0-9]{2})[- ]?[0-9]{4}[- ]?[0-9]{4}[- ]?[0-9]{4}\b",
    ],
    "api_key": [
        r"\bsk-[a-zA-Z0-9]{20,}\b",                          # OpenAI
        r"\bsk-proj-[a-zA-Z0-9\-]{20,}\b",                   # OpenAI project key
        r"\bghp_[a-zA-Z0-9]{20,}\b",                         # GitHub PAT (classic)
        r"\bgho_[a-zA-Z0-9]{20,}\b",                         # GitHub OAuth token
        r"\bAKIA[0-9A-Z]{16}\b",                             # AWS access key ID
        r"\bxoxb-[0-9]+-[0-9]+-[a-zA-Z0-9]+\b",            # Slack bot token
        r"\bAIza[0-9A-Za-z\-_]{35}\b",                      # Google API key
        # JWT (three base64url segments separated by dots)
        r"\beyJ[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]*",
    ],
}

# Compile once at import time for performance.
_COMPILED: Dict[str, List[re.Pattern]] = {
    entity_type: [re.compile(p) for p in patterns]
    for entity_type, patterns in _RAW_PATTERNS.items()
}


def _resolve_overlaps(entities: List[DetectedEntity]) -> List[DetectedEntity]:
    """
    Remove overlapping matches, keeping the longer (more specific) one.

    Entities are sorted by start position; when two overlap, the one with the
    greater span wins. This prevents, for example, a phone pattern from
    matching a digit sequence that is already part of a credit card number.

    Args:
        entities: Unsorted list of detected entities.

    Returns:
        Deduplicated, non-overlapping list sorted by start position.
    """
    if not entities:
        return entities

    # Sort: start ASC, then span length DESC (prefer longer at same start).
    sorted_ents = sorted(entities, key=lambda e: (e.start, -(e.end - e.start)))

    result: List[DetectedEntity] = []
    last_end = -1

    for entity in sorted_ents:
        if entity.start >= last_end:
            result.append(entity)
            last_end = entity.end
        # Overlapping entity: skip (the earlier/longer one already covers this range).

    return result


class RegexDetector(BaseDetector):
    """
    Built-in regex-based detector covering four entity types:

    * ``email`` — e.g. ``alice@example.com``
    * ``phone`` — North American and international formats
    * ``credit_card`` — Visa, Mastercard, Amex, Discover
    * ``api_key`` — OpenAI, GitHub PAT, AWS, Slack, Google, JWT

    This detector is used by default when no custom detectors are provided
    to :class:`~promptshield.shield.Shield`.
    """

    @property
    def supported_types(self) -> List[str]:
        """Entity types this detector can emit."""
        return list(_COMPILED.keys())

    def detect(self, text: str) -> List[DetectedEntity]:
        """
        Run all regex patterns against *text* and return matched entities.

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
                    entities.append(
                        DetectedEntity(
                            entity_type=entity_type,
                            value=match.group(),
                            start=match.start(),
                            end=match.end(),
                        )
                    )

        return _resolve_overlaps(entities)
