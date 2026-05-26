"""Abstract base classes for the detection layer."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class DetectedEntity:
    """
    Represents a single sensitive entity found in a text.

    Attributes:
        entity_type: Category label, e.g. ``"email"``, ``"phone"``,
            ``"credit_card"``, ``"api_key"``.
        value: The exact substring that was matched.
        start: Inclusive start index in the source text.
        end: Exclusive end index in the source text.
        confidence: Detector confidence in the match, 0.0–1.0.  Defaults to
            ``1.0`` (full confidence) for regex / checksum-validated matches.
            Custom detectors can emit lower values for probabilistic detections.
    """

    entity_type: str
    value: str
    start: int
    end: int
    confidence: float = 1.0


class BaseDetector(ABC):
    """
    Abstract base class for all PII / secret detectors.

    Subclass this to add custom detection logic (e.g. spaCy NER, ML models).
    Register the detector with :class:`~promptshield.shield.Shield` via
    ``shield.add_detector(my_detector)`` or pass it in the constructor.
    """

    @abstractmethod
    def detect(self, text: str) -> List[DetectedEntity]:
        """
        Scan *text* and return every sensitive entity found.

        Args:
            text: The raw input string to scan.

        Returns:
            A list of :class:`DetectedEntity` instances (may be empty).
        """
        ...

    @property
    @abstractmethod
    def supported_types(self) -> List[str]:
        """Return the entity type labels this detector can emit."""
        ...
