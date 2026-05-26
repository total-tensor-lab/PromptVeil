"""Base dataclass for compliance profile definitions."""

from dataclasses import dataclass, field
from typing import List

from ..detector.base import BaseDetector
from ..policy.models import PolicyConfig


@dataclass
class Profile:
    """
    A named compliance profile bundling a :class:`~promptshield.policy.models.PolicyConfig`
    with the detector stack required to enforce it.

    Attributes:
        name:       Machine-readable profile identifier (e.g. ``"india_dpdpa"``).
        policy:     The default policy configuration for this profile.
        detectors:  Ordered list of detectors that cover the profile's entity
                    types.  The user may override this via ``Shield(detectors=…)``.
    """

    name: str
    policy: PolicyConfig
    detectors: List[BaseDetector] = field(default_factory=list)
