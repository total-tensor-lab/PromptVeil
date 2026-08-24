"""Rich scan output — ScanResult dataclass and risk scoring."""

from dataclasses import dataclass
from typing import Dict, List

# ---------------------------------------------------------------------------
# Per-entity-type base risk weights (0.0–1.0).
# Higher weight = more sensitive / higher regulatory exposure.
# ---------------------------------------------------------------------------
_RISK_WEIGHTS: Dict[str, float] = {
    "credit_card": 0.90,
    "api_key":     0.85,
    "in_aadhaar":  0.90,
    "in_passport": 0.85,
    "ssn":         0.90,
    "in_pan":      0.80,
    "us_passport": 0.80,
    "in_voter_id": 0.70,
    "us_ein":      0.65,
    "in_gstin":    0.60,
    "in_ifsc":     0.50,
    "email":       0.40,
    "phone":       0.40,
    "in_phone":    0.40,
}
_DEFAULT_WEIGHT = 0.35


@dataclass(frozen=True)
class EntityResult:
    """
    Per-entity detail inside a :class:`ScanResult`.

    Attributes:
        entity_type:  E.g. ``"email"``, ``"credit_card"``.
        action:       ``"mask"`` or ``"allow"`` (``"block"`` always raises
                      before a ScanResult is produced).
        start:        Start index in the *original* prompt.
        end:          End index in the *original* prompt.
        masked_value: The masked/redacted form, or the original value when
                      action is ``"allow"``.
        confidence:   Detector confidence (0.0–1.0).
    """

    entity_type: str
    action: str
    start: int
    end: int
    masked_value: str
    confidence: float


@dataclass(frozen=True)
class ScanResult:
    """
    Rich output from :meth:`~promptveil.shield.Shield.scan_detailed`.

    Attributes:
        safe_text:   Sanitised prompt (entities replaced by masked forms).
        entities:    All detected entities with their resolved actions.
        risk_score:  Composite float 0.0–1.0.  Uses a probabilistic union
                     model — each additional sensitive entity pushes the score
                     closer to 1.0.  Allow-actioned entities contribute at
                     30 % of their base weight.
        risk_level:  ``"NONE"`` | ``"LOW"`` | ``"MEDIUM"`` | ``"HIGH"`` |
                     ``"CRITICAL"``.
        was_mutated: ``True`` if any masking changed the original text.
    """

    safe_text: str
    entities: List[EntityResult]
    risk_score: float
    risk_level: str
    was_mutated: bool


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _compute_risk_score(entity_results: List[EntityResult]) -> float:
    """
    Compute a composite risk score using a probabilistic union model.

    ``score = 1 - product(1 - effective_weight_i)``

    Allow-actioned entities contribute at 30 % of their base weight because
    the data passed through policy — it is still present in the prompt.

    Args:
        entity_results: Entities detected (after block check).

    Returns:
        Float in [0.0, 1.0], rounded to 4 decimal places.
    """
    if not entity_results:
        return 0.0

    product = 1.0
    for er in entity_results:
        base = _RISK_WEIGHTS.get(er.entity_type, _DEFAULT_WEIGHT)
        # Allow-actioned entities carry reduced weight.
        effective = base * (0.3 if er.action == "allow" else 1.0) * er.confidence
        product *= 1.0 - max(0.0, min(1.0, effective))

    return round(1.0 - product, 4)


def _risk_level(score: float) -> str:
    """Map a numeric risk score to a human-readable level."""
    if score == 0.0:
        return "NONE"
    if score < 0.30:
        return "LOW"
    if score < 0.60:
        return "MEDIUM"
    if score < 0.85:
        return "HIGH"
    return "CRITICAL"
